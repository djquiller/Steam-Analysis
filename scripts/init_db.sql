-- =====================================================================
-- 建库建表脚本（可重复执行）
--
-- 做什么：创建两个库和 ods / dwd 两层的表。ads 层在聚合阶段另建。
-- 为什么分两个库：
--   steam_ods  原始数据层，只有 ETL（etl_writer）读写；
--   steam      dwd 明细层 + ads 聚合层，后端 api_reader 对整个库只有 SELECT。
--   MySQL 不支持按表名前缀授权，分库后用库级授权就能实现
--   "api_reader 只读 dwd/ads"，新增表也不用逐表补授权。
-- 字符集：一律 utf8mb4 / utf8mb4_0900_ai_ci（见 docs/schema.md 全局口径）。
--
-- 执行（root，在仓库根目录）：mysql -u root -p -e "source scripts/init_db.sql"
--   （PowerShell 不支持 `<` 输入重定向，所以用 mysql 自带的 source 命令）
-- 账号创建见 storage/README.md，密码不写进仓库。
-- =====================================================================

CREATE DATABASE IF NOT EXISTS steam_ods
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE IF NOT EXISTS steam
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- ods 层：原始数据，字段名与源文件一致（转为 snake_case），不做清洗
-- ---------------------------------------------------------------------
USE steam_ods;

-- Kaggle 游戏集 games.csv（FronkonGames）。
-- 注意：源文件表头把 "Discount" 和 "DLC count" 粘成了一列，导入脚本已按 40 列修正。
-- 列表类字段（语言、类型、标签等）保留源文件的原始字符串，拆分留给清洗阶段。
CREATE TABLE IF NOT EXISTS ods_game_kaggle (
  app_id                      INT UNSIGNED  NOT NULL,
  name                        VARCHAR(512),
  release_date                VARCHAR(32)   COMMENT '原始文本，如 "Aug 1, 2023"',
  estimated_owners            VARCHAR(32)   COMMENT '原始区间，如 "20000 - 50000"',
  peak_ccu                    INT,
  required_age                INT,
  price                       DECIMAL(10,2) COMMENT '美元',
  discount                    INT,
  dlc_count                   INT,
  about_the_game              MEDIUMTEXT,
  supported_languages         TEXT,
  full_audio_languages        TEXT,
  reviews                     TEXT,
  header_image                VARCHAR(1024),
  website                     VARCHAR(1024),
  support_url                 VARCHAR(1024),
  support_email               VARCHAR(512),
  windows                     TINYINT(1),
  mac                         TINYINT(1),
  linux                       TINYINT(1),
  metacritic_score            INT,
  metacritic_url              VARCHAR(1024),
  user_score                  INT,
  positive                    INT,
  negative                    INT,
  score_rank                  VARCHAR(32),
  achievements                INT,
  recommendations             INT,
  notes                       TEXT,
  average_playtime_forever    INT           COMMENT '分钟',
  average_playtime_two_weeks  INT,
  median_playtime_forever     INT,
  median_playtime_two_weeks   INT,
  developers                  TEXT,
  publishers                  TEXT,
  categories                  TEXT,
  genres                      TEXT          COMMENT '逗号分隔',
  tags                        TEXT,
  screenshots                 MEDIUMTEXT,
  movies                      MEDIUMTEXT,
  loaded_at                   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (app_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Kaggle FronkonGames 游戏集原始数据';

-- Kaggle 评论集 reviews-*.parquet（sergiodelcarpio）。
-- 只保留分析用的字段：评论原文（体积最大）与评论者哈希 ID（隐私）不入库。
-- src_shard 记录来自第几个分片，便于按分片重跑（先删该分片再导入）。
CREATE TABLE IF NOT EXISTS ods_review_kaggle (
  review_id                    BIGINT UNSIGNED NOT NULL,
  game_id                      INT UNSIGNED    NOT NULL,
  is_positive                  TINYINT(1),
  language                     VARCHAR(32),
  reviewed_at                  DATETIME        COMMENT 'UTC',
  playtime_at_review           INT             COMMENT '分钟',
  playtime_forever             INT             COMMENT '分钟',
  votes_up                     INT,
  steam_purchase               TINYINT(1),
  received_for_free            TINYINT(1),
  written_during_early_access  TINYINT(1),
  src_shard                    SMALLINT        NOT NULL,
  PRIMARY KEY (review_id),
  KEY idx_src_shard (src_shard)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Kaggle 评论集原始元数据（不含原文与用户 ID）';

-- 评论原文抽样：每款游戏最多保留 k 条（供关键词分析与情感模型）。
-- sample_key 是 review_id 的确定性哈希，每款游戏保留 sample_key 最小的 k 条，
-- 等价于每款游戏均匀随机抽 k 条；跨分片可合并、重跑结果不变。
CREATE TABLE IF NOT EXISTS ods_review_text_sample (
  review_id    BIGINT UNSIGNED NOT NULL,
  game_id      INT UNSIGNED    NOT NULL,
  language     VARCHAR(32),
  is_positive  TINYINT(1),
  sample_key   BIGINT UNSIGNED NOT NULL,
  review       MEDIUMTEXT,
  src_shard    SMALLINT        NOT NULL,
  PRIMARY KEY (review_id),
  KEY idx_game_key (game_id, sample_key),
  KEY idx_src_shard (src_shard)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='评论原文分层抽样（每款游戏最多 k 条）';

-- ETL 进度：scripts/load_data.py 每完成一个步骤记一行，中断后重跑会跳过已完成的步骤。
CREATE TABLE IF NOT EXISTS etl_progress (
  step         VARCHAR(32)  NOT NULL COMMENT 'ods_review / text_sample / dwd_review …',
  shard        SMALLINT     NOT NULL COMMENT '不分片的步骤记 -1',
  rows_done    BIGINT,
  elapsed_sec  DECIMAL(10,1),
  finished_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (step, shard)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='ETL 断点续跑进度';

-- ---------------------------------------------------------------------
-- dwd 层：清洗后的明细（字段口径见 docs/schema.md）
-- ---------------------------------------------------------------------
USE steam;

CREATE TABLE IF NOT EXISTS dwd_game (
  appid                  INT UNSIGNED  NOT NULL,
  name                   VARCHAR(512)  NOT NULL,
  release_date           DATE,
  release_year           SMALLINT      COMMENT '未发行或日期缺失为 NULL，不进 ads',
  price_usd              DECIMAL(10,2) NOT NULL DEFAULT 0,
  price_bucket           VARCHAR(8)    NOT NULL COMMENT 'free / lt10 / 10_30 / 30_60 / ge60',
  owners_low             INT UNSIGNED,
  owners_high            INT UNSIGNED,
  owners_mid             INT UNSIGNED  COMMENT 'SteamSpy 区间中值',
  peak_ccu               INT UNSIGNED,
  positive               INT UNSIGNED  NOT NULL DEFAULT 0,
  negative               INT UNSIGNED  NOT NULL DEFAULT 0,
  avg_playtime_min       INT UNSIGNED,
  median_playtime_min    INT UNSIGNED,
  required_age           TINYINT UNSIGNED,
  dlc_count              INT UNSIGNED,
  achievements           INT UNSIGNED,
  num_languages          SMALLINT UNSIGNED,
  on_windows             TINYINT(1),
  on_mac                 TINYINT(1),
  on_linux               TINYINT(1),
  metacritic_score       TINYINT UNSIGNED,
  developer              VARCHAR(255)  COMMENT '取第一个开发商',
  publisher              VARCHAR(255)  COMMENT '取第一个发行商',
  header_image           VARCHAR(1024),
  PRIMARY KEY (appid),
  KEY idx_year_bucket (release_year, price_bucket)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='游戏明细';

CREATE TABLE IF NOT EXISTS dwd_game_genre (
  appid  INT UNSIGNED NOT NULL,
  genre  VARCHAR(64)  NOT NULL,
  PRIMARY KEY (appid, genre),
  KEY idx_genre_appid (genre, appid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='游戏 × 类型（一款游戏多个类型时拆成多行）';

-- 聚簇主键 (appid, review_id)：同一款游戏的评论物理上相邻，
-- 按游戏聚合、详情页按游戏查评论走势都是顺序读。
CREATE TABLE IF NOT EXISTS dwd_review (
  appid                   INT UNSIGNED    NOT NULL,
  review_id               BIGINT UNSIGNED NOT NULL,
  language                VARCHAR(32)     NOT NULL,
  voted_up                TINYINT(1)      NOT NULL,
  playtime_at_review_min  INT UNSIGNED,
  timestamp_created       DATETIME        NOT NULL COMMENT 'UTC',
  PRIMARY KEY (appid, review_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='评论明细（元数据）';

CREATE TABLE IF NOT EXISTS dwd_ccu_snapshot (
  appid         INT UNSIGNED NOT NULL,
  snapshot_at   DATETIME     NOT NULL COMMENT 'UTC，整点',
  player_count  INT UNSIGNED NOT NULL,
  PRIMARY KEY (appid, snapshot_at),
  KEY idx_snapshot_at (snapshot_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='在线人数快照';

CREATE TABLE IF NOT EXISTS dwd_price_history (
  appid          INT UNSIGNED  NOT NULL,
  snapshot_date  DATE          NOT NULL,
  price_usd      DECIMAL(10,2) NOT NULL,
  PRIMARY KEY (appid, snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='价格历史（仅增量采集后有数据）';

-- =====================================================================
-- 建库建表脚本（可重复执行）
--
-- 做什么：创建两个库和 ods / dwd / ads 三层的表。
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

-- ---------------------------------------------------------------------
-- ads 层：面向大屏的聚合表与模型结果表（字段口径见 docs/schema.md）
--
-- 聚合表的主键以 (release_year, genre, price_bucket) 开头：后端按这三列过滤后
-- 再 SUM … GROUP BY。genre = '__ALL__' 是预先算好的汇总行，每款游戏只计一次，
-- 用来避免多类型游戏按类型相加时重复计数。
-- 聚合表只存计数和合计（可以相加），均价、好评率、分位数由后端现算。
-- ---------------------------------------------------------------------

-- KPI 卡：固定只有 id = 1 一行；不同来源的列由不同脚本各自更新。
CREATE TABLE IF NOT EXISTS ads_kpi_overview (
  id               TINYINT UNSIGNED NOT NULL COMMENT '固定为 1',
  game_cnt         INT UNSIGNED     NOT NULL COMMENT '游戏总数（款）：有发行年份的游戏',
  review_cnt       BIGINT UNSIGNED           COMMENT '评论总数（条）：dwd_review 行数；评论侧聚合前为 NULL',
  owners_total     BIGINT UNSIGNED  NOT NULL COMMENT '估算玩家总量（份）：owners_mid 之和，同一玩家多款游戏重复计',
  online_peak_24h  INT UNSIGNED              COMMENT '近 24 小时采集名单内游戏在线人数之和的最大值（人）',
  online_peak_at   DATETIME                  COMMENT '峰值出现的采集时刻，UTC',
  updated_at       DATETIME         NOT NULL COMMENT 'UTC',
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='KPI 概览（单行）';

CREATE TABLE IF NOT EXISTS ads_yearly_release (
  release_year  SMALLINT       NOT NULL,
  genre         VARCHAR(64)    NOT NULL COMMENT '类型名或 __ALL__',
  price_bucket  VARCHAR(8)     NOT NULL,
  game_cnt      INT UNSIGNED   NOT NULL COMMENT '发行量（款）',
  price_sum     DECIMAL(14,2)  NOT NULL COMMENT '价格合计（美元），均价 = price_sum / game_cnt',
  PRIMARY KEY (release_year, genre, price_bucket)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='历年发行量与价格合计';

-- 本身按类型展示，不设 __ALL__ 行。
CREATE TABLE IF NOT EXISTS ads_genre_heat (
  release_year  SMALLINT         NOT NULL,
  genre         VARCHAR(64)      NOT NULL,
  price_bucket  VARCHAR(8)       NOT NULL,
  game_cnt      INT UNSIGNED     NOT NULL COMMENT '游戏数（款），多类型游戏在每个类型下各计一次',
  owners_sum    BIGINT UNSIGNED  NOT NULL COMMENT 'owners_mid 之和（份）',
  review_cnt    BIGINT UNSIGNED  NOT NULL COMMENT 'positive + negative 之和（条），Steam 官方总数',
  positive_cnt  BIGINT UNSIGNED  NOT NULL COMMENT 'positive 之和（条）',
  PRIMARY KEY (release_year, genre, price_bucket)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='类型热度';

-- 游戏粒度：收录全部有发行年份的游戏，任意筛选组合下的 Top N 都精确。
-- 筛类型时后端用 EXISTS 关联 dwd_game_genre。
CREATE TABLE IF NOT EXISTS ads_top_sellers (
  appid         INT UNSIGNED   NOT NULL,
  name          VARCHAR(512)   NOT NULL,
  release_year  SMALLINT       NOT NULL,
  price_bucket  VARCHAR(8)     NOT NULL,
  price_usd     DECIMAL(10,2)  NOT NULL,
  owners_mid    INT UNSIGNED            COMMENT '拥有者（份），SteamSpy 区间中值',
  review_cnt    INT UNSIGNED   NOT NULL COMMENT 'positive + negative（条）',
  positive_cnt  INT UNSIGNED   NOT NULL COMMENT 'positive（条）',
  peak_ccu      INT UNSIGNED            COMMENT '历史峰值在线（人）',
  ccu_latest    INT UNSIGNED            COMMENT '最新采集时刻的在线人数（人），每小时更新',
  ccu_at        DATETIME                COMMENT 'ccu_latest 的采集时刻，UTC',
  PRIMARY KEY (appid),
  KEY idx_owners (owners_mid, review_cnt),
  KEY idx_ccu (ccu_latest),
  KEY idx_year_bucket (release_year, price_bucket)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='热销榜（游戏粒度）';

CREATE TABLE IF NOT EXISTS ads_ccu_latest (
  appid              INT UNSIGNED  NOT NULL,
  name               VARCHAR(512)  NOT NULL,
  player_count       INT UNSIGNED  NOT NULL COMMENT '最新采集时刻的在线人数（人）',
  player_count_prev  INT UNSIGNED           COMMENT '上一个采集时刻的在线人数（人）',
  snapshot_at        DATETIME      NOT NULL COMMENT '最新采集时刻，UTC，全表相同',
  PRIMARY KEY (appid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='实时在线榜（最新快照 Top 100）';

CREATE TABLE IF NOT EXISTS ads_game_cluster (
  appid             INT UNSIGNED      NOT NULL,
  name              VARCHAR(512)      NOT NULL,
  release_year      SMALLINT          NOT NULL,
  price_bucket      VARCHAR(8)        NOT NULL,
  cluster_id        TINYINT UNSIGNED  NOT NULL COMMENT '簇编号，从 0 开始',
  cluster_label     VARCHAR(32)       NOT NULL COMMENT '簇的业务标签',
  x                 FLOAT             NOT NULL COMMENT 'PCA 第一主成分',
  y                 FLOAT             NOT NULL COMMENT 'PCA 第二主成分',
  price_usd         DECIMAL(10,2)     NOT NULL,
  positive_rate     DECIMAL(5,4)      NOT NULL COMMENT '好评率，0–1',
  owners_mid        INT UNSIGNED      NOT NULL COMMENT '拥有者（份）',
  avg_playtime_min  INT UNSIGNED      NOT NULL COMMENT '平均游玩时长（分钟）',
  sample_key        INT UNSIGNED      NOT NULL COMMENT 'CRC32(appid)，散点抽样用',
  PRIMARY KEY (appid),
  KEY idx_year_bucket (release_year, price_bucket),
  KEY idx_cluster (cluster_id),
  KEY idx_sample_key (sample_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='游戏聚类结果（游戏粒度）';

-- 1% 分箱：分箱计数可以相加，直方图和箱线图的五数都由它推出。
CREATE TABLE IF NOT EXISTS ads_rating_dist (
  release_year  SMALLINT          NOT NULL,
  genre         VARCHAR(64)       NOT NULL COMMENT '类型名或 __ALL__',
  price_bucket  VARCHAR(8)        NOT NULL,
  rating_bin    TINYINT UNSIGNED  NOT NULL COMMENT '好评率分箱 0–99，100% 归入 99',
  game_cnt      INT UNSIGNED      NOT NULL COMMENT '游戏数（款），只统计评论总数 >= 10 的游戏',
  PRIMARY KEY (release_year, genre, price_bucket, rating_bin)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='好评率分布（1% 分箱）';

CREATE TABLE IF NOT EXISTS ads_review_lang (
  release_year  SMALLINT         NOT NULL COMMENT '所评游戏的发行年份',
  genre         VARCHAR(64)      NOT NULL COMMENT '类型名或 __ALL__',
  price_bucket  VARCHAR(8)       NOT NULL,
  language      VARCHAR(32)      NOT NULL,
  review_cnt    BIGINT UNSIGNED  NOT NULL COMMENT '评论数（条）',
  positive_cnt  BIGINT UNSIGNED  NOT NULL COMMENT '其中 voted_up = 1 的评论数（条）',
  PRIMARY KEY (release_year, genre, price_bucket, language)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='评论语言分布';

CREATE TABLE IF NOT EXISTS ads_playtime_dist (
  release_year  SMALLINT          NOT NULL COMMENT '所评游戏的发行年份',
  genre         VARCHAR(64)       NOT NULL COMMENT '类型名或 __ALL__',
  price_bucket  VARCHAR(8)        NOT NULL,
  playtime_bin  TINYINT UNSIGNED  NOT NULL COMMENT '时长分箱 0–10，定义见 docs/schema.md',
  review_cnt    BIGINT UNSIGNED   NOT NULL COMMENT '评论数（条）',
  PRIMARY KEY (release_year, genre, price_bucket, playtime_bin)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='写评论时的游玩时长分布';

CREATE TABLE IF NOT EXISTS ads_review_heatmap (
  release_year  SMALLINT          NOT NULL COMMENT '所评游戏的发行年份',
  genre         VARCHAR(64)       NOT NULL COMMENT '类型名或 __ALL__',
  price_bucket  VARCHAR(8)        NOT NULL,
  weekday       TINYINT UNSIGNED  NOT NULL COMMENT '0 = 周一 … 6 = 周日，UTC',
  hour          TINYINT UNSIGNED  NOT NULL COMMENT '0–23，UTC',
  review_cnt    BIGINT UNSIGNED   NOT NULL COMMENT '评论数（条）',
  PRIMARY KEY (release_year, genre, price_bucket, weekday, hour)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='评论活跃时段（星期 × 小时）';

-- 聚簇主键 (appid, month_start)：详情页按 appid 范围读取一款游戏的各月。
CREATE TABLE IF NOT EXISTS ads_game_review_trend (
  appid         INT UNSIGNED  NOT NULL,
  month_start   DATE          NOT NULL COMMENT '评论发表月份的第一天，UTC',
  review_cnt    INT UNSIGNED  NOT NULL COMMENT '该月评论数（条）',
  positive_cnt  INT UNSIGNED  NOT NULL COMMENT '该月 voted_up = 1 的评论数（条）',
  PRIMARY KEY (appid, month_start)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='单款游戏评论月度走势';

CREATE TABLE IF NOT EXISTS ads_hot_pred (
  appid       INT UNSIGNED  NOT NULL,
  hot_prob    DECIMAL(5,4)  NOT NULL COMMENT '热销概率，0–1',
  hot_pred    TINYINT(1)    NOT NULL COMMENT '预测标签，1 = 热销',
  hot_actual  TINYINT(1)    NOT NULL COMMENT '实际标签，owners_mid 不低于第 90 百分位',
  is_test     TINYINT(1)    NOT NULL COMMENT '1 = 在测试集里（训练时没见过）',
  model_name  VARCHAR(32)   NOT NULL COMMENT '与 ads_model_metrics.model_name 一致',
  PRIMARY KEY (appid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='热销预测结果';

CREATE TABLE IF NOT EXISTS ads_model_metrics (
  model_name    VARCHAR(32)  NOT NULL COMMENT '如 hot_rf / hot_lr / sentiment_lr / cluster_kmeans',
  metric        VARCHAR(32)  NOT NULL COMMENT '如 accuracy / f1 / auc / silhouette',
  metric_value  DOUBLE       NOT NULL,
  updated_at    DATETIME     NOT NULL COMMENT 'UTC',
  PRIMARY KEY (model_name, metric)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='模型评估指标（答辩展示）';

CREATE TABLE IF NOT EXISTS ads_review_sentiment (
  appid         INT UNSIGNED  NOT NULL,
  sample_cnt    INT UNSIGNED  NOT NULL COMMENT '参与打分的评论条数',
  positive_cnt  INT UNSIGNED  NOT NULL COMMENT '判为正向的条数，占比 = positive_cnt / sample_cnt',
  method        VARCHAR(16)   NOT NULL COMMENT 'model = 情感模型；voted_up = 降级统计',
  PRIMARY KEY (appid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='评论情感正向占比';

-- 键值表：各脚本只写自己负责的键，不清空整表。
CREATE TABLE IF NOT EXISTS ads_meta (
  meta_key    VARCHAR(64)   NOT NULL COMMENT 'data_updated_at / ccu_updated_at / rows.<表名>',
  meta_value  VARCHAR(255)  NOT NULL,
  updated_at  DATETIME      NOT NULL COMMENT 'UTC',
  PRIMARY KEY (meta_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='元信息：数据更新时间、各表行数';

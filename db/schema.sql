-- =====================================================================
-- RythLAB 曲DB スキーマ（ロリポップ MySQL 用）
--   対象機種: CHUNITHM / オンゲキ / maimai でらっくす
--   データ元: https://reiwa.f5.si/api.html （楽曲情報API）
--   設計の説明: docs/db-design.md
--
-- 使い方: phpMyAdmin の「インポート」または
--   mysql -u USER -p DB_NAME < db/schema.sql
-- 何度流しても既存データは消えない（CREATE TABLE IF NOT EXISTS）。
-- MySQL 5.7 / 8.0 のどちらでも動く書き方にしている。
-- =====================================================================

SET NAMES utf8mb4;

-- ---------------------------------------------------------------------
-- 機種
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS games (
  id   TINYINT UNSIGNED NOT NULL COMMENT '機種ID（固定値）',
  code VARCHAR(16)      NOT NULL COMMENT '機種コード（取り込みSQL・APIで使う）',
  name VARCHAR(50)      NOT NULL COMMENT '表示名',
  PRIMARY KEY (id),
  UNIQUE KEY uq_games_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='機種マスタ';

INSERT INTO games (id, code, name) VALUES
  (1, 'chunithm', 'CHUNITHM'),
  (2, 'ongeki',   'オンゲキ'),
  (3, 'maimai',   'maimai でらっくす')
ON DUPLICATE KEY UPDATE code = VALUES(code), name = VALUES(name);

-- ---------------------------------------------------------------------
-- 機種のバージョン（稼働開始日つき）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS game_versions (
  id           SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  game_id      TINYINT UNSIGNED  NOT NULL,
  name         VARCHAR(100)      NOT NULL COMMENT '例: CHUNITHM X-VERSE',
  release_date DATE              NOT NULL COMMENT '稼働開始日',
  PRIMARY KEY (id),
  UNIQUE KEY uq_game_versions (game_id, name),
  CONSTRAINT fk_game_versions_game FOREIGN KEY (game_id) REFERENCES games (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='機種のバージョン一覧';

-- ---------------------------------------------------------------------
-- 楽曲（機種をまたいで1曲1行。アプリが再生・プレイリストで扱う単位）
--   例: 「千本桜」は3機種に収録されているが songs では1行
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS songs (
  id               INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  match_key        CHAR(40) CHARACTER SET ascii COLLATE ascii_bin NOT NULL
                   COMMENT '同一曲判定キー（正規化した曲名+アーティストのSHA-1）。取り込みで使う',
  title            VARCHAR(255)      NOT NULL COMMENT '曲名（最初に取り込んだ機種の表記）',
  artist           VARCHAR(255)      NOT NULL COMMENT 'アーティスト（同上）',
  youtube_video_id VARCHAR(16)       NULL     COMMENT '再生に使うYouTube動画ID（アプリ側で登録）',
  chorus_start_sec SMALLINT UNSIGNED NULL     COMMENT 'サビ開始位置（秒）。ショート再生の開始位置（アプリ側で登録）',
  created_at       DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_songs_match_key (match_key),
  KEY idx_songs_title (title),
  KEY idx_songs_artist (artist)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='楽曲（機種横断）';

-- ---------------------------------------------------------------------
-- 機種ごとの収録曲（データ元の1曲 = 1行）
--   CHUNITHM の WORLD'S END は元データで別エントリなので別行（is_worlds_end=1）。
--   オンゲキの LUNATIC は元データで同じIDの別エントリだが、1行にまとめる。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS game_songs (
  id            INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  game_id       TINYINT UNSIGNED  NOT NULL,
  source_id     VARCHAR(32)       NOT NULL COMMENT 'データ元の曲ID（meta.id）',
  song_id       INT UNSIGNED      NOT NULL COMMENT '対応する songs.id',
  title         VARCHAR(255)      NOT NULL COMMENT 'この機種での曲名表記',
  artist        VARCHAR(255)      NOT NULL COMMENT 'この機種でのアーティスト表記',
  genre         VARCHAR(64)       NOT NULL COMMENT 'この機種でのジャンル',
  release_date  DATE              NOT NULL COMMENT 'この機種への収録日',
  version_id    SMALLINT UNSIGNED NULL     COMMENT '収録バージョン（収録日から推定）',
  is_bonus      TINYINT(1)        NOT NULL DEFAULT 0 COMMENT 'オンゲキのボーナストラック',
  is_worlds_end TINYINT(1)        NOT NULL DEFAULT 0 COMMENT 'CHUNITHM の WORLD''S END 譜面',
  is_available  TINYINT(1)        NOT NULL DEFAULT 1 COMMENT '最新の取り込みで元データに存在したか（0 = 削除された曲）',
  created_at    DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_game_songs_source (game_id, source_id),
  KEY idx_game_songs_song (song_id),
  KEY idx_game_songs_release (release_date),
  CONSTRAINT fk_game_songs_game    FOREIGN KEY (game_id)    REFERENCES games (id),
  CONSTRAINT fk_game_songs_song    FOREIGN KEY (song_id)    REFERENCES songs (id),
  CONSTRAINT fk_game_songs_version FOREIGN KEY (version_id) REFERENCES game_versions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='機種ごとの収録曲';

-- ---------------------------------------------------------------------
-- 譜面（難易度ごと）
--   chart_type: maimai のスタンダード(STD)/でらっくす(DX)。他機種は常に STD
--   difficulty: BAS/ADV/EXP/MAS 共通、ULT=ULTIMA, WE=WORLD'S END,
--               LUN=LUNATIC(オンゲキ), REMAS=Re:MASTER(maimai)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS charts (
  id               INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  game_song_id     INT UNSIGNED  NOT NULL,
  chart_type       ENUM('STD','DX') NOT NULL DEFAULT 'STD',
  difficulty       ENUM('BAS','ADV','EXP','MAS','ULT','REMAS','LUN','WE') NOT NULL,
  level            DECIMAL(3,1)  NULL COMMENT 'レベル（13.5 = 13+）。WORLD''S END は NULL',
  const            DECIMAL(3,1)  NULL COMMENT '譜面定数。WORLD''S END は NULL',
  is_const_unknown TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '譜面定数が未確定（仮の値）',
  max_combo        SMALLINT UNSIGNED NULL COMMENT '最大コンボ数（CHUNITHM のみ）',
  added_date       DATE          NULL COMMENT '譜面の追加日（オンゲキ LUNATIC は曲と別日になる）',
  PRIMARY KEY (id),
  UNIQUE KEY uq_charts (game_song_id, chart_type, difficulty),
  CONSTRAINT fk_charts_game_song FOREIGN KEY (game_song_id) REFERENCES game_songs (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='譜面';

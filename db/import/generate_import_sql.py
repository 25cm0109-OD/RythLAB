#!/usr/bin/env python3
"""reiwa.f5.si の楽曲JSONから、RythLAB 曲DB への取り込みSQLを生成する。

使い方:
    python3 db/import/generate_import_sql.py            # JSONをダウンロードして生成
    python3 db/import/generate_import_sql.py --offline  # db/import/raw/ の保存済みJSONから生成

出力: db/import/import.sql（phpMyAdmin の「インポート」で流す）
外部ライブラリ不要（Python 3.8 以上の標準ライブラリのみ）。
詳細は docs/db-design.md を参照。
"""
import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

BASE_URL = "https://reiwa.f5.si/"
HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "raw"
OUT_FILE = HERE / "import.sql"

# 並び順 = songs.title / artist に採用する表記の優先順
GAMES = [
    # (機種コード, 楽曲JSON, バージョンJSON)
    ("chunithm", "chunirec_all.json", "chunithm_versions.json"),
    ("maimai", "maimai_all.json", "maimai_versions.json"),
    ("ongeki", "ongeki_all.json", "ongeki_versions.json"),
]

DIFFICULTIES = {"BAS", "ADV", "EXP", "MAS", "ULT", "REMAS", "LUN", "WE"}
WE_SUFFIX = re.compile(r"【.】$")          # 例: 「B.B.K.K.B.K.K.【戻】」
WORK_NOTE = re.compile(r"「[^」]*」(より)?")  # 例: 「USAO「Arcaea」」の作品名部分


# ---------------------------------------------------------------- 入力
def load_json(name, offline):
    path = RAW_DIR / name
    if not offline:
        req = urllib.request.Request(BASE_URL + name, headers={"User-Agent": "RythLAB-importer"})
        with urllib.request.urlopen(req, timeout=60) as res:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(res.read())
        time.sleep(1)  # 配布元に負荷をかけないよう間隔をあける
    return json.loads(path.read_text(encoding="utf-8-sig"))


# ---------------------------------------------------------------- 同一曲判定
def norm(s):
    """全角/半角・大文字/小文字・空白の違いを吸収する。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s)).casefold()


def match_key(title, artist):
    artist = WORK_NOTE.sub("", unicodedata.normalize("NFKC", artist))
    raw = norm(title) + "\x1f" + norm(artist)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def version_for(release, versions):
    """収録日以前で最新のバージョン名（収録日からの推定）。"""
    name = versions[0]["version"]
    for v in versions:
        if v["release"] <= release:
            name = v["version"]
    return name


def num(v):
    """0 は「未設定」（WORLD'S END のレベル等）なので NULL にする。"""
    return None if v in (None, 0) else float(v)


# ---------------------------------------------------------------- 変換
def convert(offline):
    songs = {}        # match_key -> (title, artist)
    game_songs = []   # dict
    charts = []       # dict
    versions_rows = []

    def add_song(title, artist):
        key = match_key(title, artist)
        songs.setdefault(key, (title, artist))
        return key

    def add_chart(game, source_id, chart_type, diff, c, added):
        if diff not in DIFFICULTIES:
            raise ValueError(f"未知の難易度 {diff} ({game} {source_id})")
        charts.append(dict(
            game=game, source_id=source_id, chart_type=chart_type, difficulty=diff,
            level=num(c.get("level")), const=num(c.get("const")),
            is_const_unknown=int(bool(c.get("is_const_unknown"))),
            max_combo=c.get("maxcombo"), added_date=added,
        ))

    for game, songs_file, versions_file in GAMES:
        versions = sorted(load_json(versions_file, offline), key=lambda v: v["release"])
        versions_rows += [dict(game=game, name=v["version"], release=v["release"]) for v in versions]
        entries = load_json(songs_file, offline)

        if game == "ongeki":
            # LUNATIC は同じIDの別エントリになっているので、IDごとにまとめる
            grouped = {}
            for e in entries:
                grouped.setdefault(e["meta"]["id"], []).append(e)
            entries = []
            for group in grouped.values():
                group.sort(key=lambda e: set(e["data"]) == {"LUN"})  # 通常譜面のあるエントリを先頭に
                entries.append(group)
        else:
            entries = [[e] for e in entries]

        for group in entries:
            meta = group[0]["meta"]
            source_id = str(meta["id"])
            title, artist = meta["title"], meta["artist"]
            is_we = game == "chunithm" and "WE" in group[0]["data"]
            # WORLD'S END は「曲名【字】」なので、元の曲と同じ songs 行に紐づける
            key = add_song(WE_SUFFIX.sub("", title) if is_we else title, artist)
            game_songs.append(dict(
                game=game, source_id=source_id, song_key=key, title=title, artist=artist,
                genre=meta["genre"], release=meta["release"],
                version=version_for(meta["release"], versions),
                is_bonus=int(bool(meta.get("is_bonus"))), is_worlds_end=int(is_we),
            ))
            for e in group:
                added = e["meta"]["release"]
                if game == "maimai":
                    for chart_type in ("std", "dx"):
                        for diff, c in e["data"].get(chart_type, {}).items():
                            add_chart(game, source_id, chart_type.upper(), diff, c, added)
                else:
                    for diff, c in e["data"].items():
                        add_chart(game, source_id, "STD", diff, c, added)

    return versions_rows, songs, game_songs, charts


# ---------------------------------------------------------------- SQL 出力
def q(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return f"{v:.1f}"
    s = str(v).replace("\\", "\\\\").replace("'", "''").replace("\0", "\\0")
    s = s.replace("\n", "\\n").replace("\r", "\\r")
    return "'" + s + "'"


def bulk_insert(table, cols, rows, chunk=300):
    out = []
    for i in range(0, len(rows), chunk):
        values = ",\n".join("(" + ",".join(q(v) for v in r) + ")" for r in rows[i:i + chunk])
        out.append(f"INSERT INTO {table} ({','.join(cols)}) VALUES\n{values};")
    return "\n".join(out)


def build_sql(versions_rows, songs, game_songs, charts):
    codes = ",".join(q(g[0]) for g in GAMES)
    tbl = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
    parts = [f"""-- RythLAB 曲DB 取り込みSQL（db/import/generate_import_sql.py で自動生成。手で編集しない）
-- 生成日時: {time.strftime('%Y-%m-%d %H:%M:%S')}
-- データ元: {BASE_URL}api.html
-- 先に db/schema.sql を流しておくこと。何度流しても重複しない（上書き更新）。
SET NAMES utf8mb4;

-- 1) 作業用テーブル
DROP TABLE IF EXISTS import_versions, import_songs, import_game_songs, import_charts;
CREATE TABLE import_versions (game_code VARCHAR(16), name VARCHAR(100), release_date DATE) {tbl};
CREATE TABLE import_songs (match_key CHAR(40) CHARACTER SET ascii COLLATE ascii_bin, title VARCHAR(255), artist VARCHAR(255)) {tbl};
CREATE TABLE import_game_songs (game_code VARCHAR(16), source_id VARCHAR(32), song_key CHAR(40) CHARACTER SET ascii COLLATE ascii_bin,
  title VARCHAR(255), artist VARCHAR(255), genre VARCHAR(64), release_date DATE, version_name VARCHAR(100),
  is_bonus TINYINT(1), is_worlds_end TINYINT(1), KEY (game_code, source_id)) {tbl};
CREATE TABLE import_charts (game_code VARCHAR(16), source_id VARCHAR(32), chart_type VARCHAR(8), difficulty VARCHAR(8),
  level DECIMAL(3,1), const DECIMAL(3,1), is_const_unknown TINYINT(1), max_combo SMALLINT UNSIGNED, added_date DATE) {tbl};
"""]
    parts.append(bulk_insert("import_versions", ["game_code", "name", "release_date"],
                             [(r["game"], r["name"], r["release"]) for r in versions_rows]))
    parts.append(bulk_insert("import_songs", ["match_key", "title", "artist"],
                             [(k, t, a) for k, (t, a) in songs.items()]))
    parts.append(bulk_insert(
        "import_game_songs",
        ["game_code", "source_id", "song_key", "title", "artist", "genre", "release_date",
         "version_name", "is_bonus", "is_worlds_end"],
        [(g["game"], g["source_id"], g["song_key"], g["title"], g["artist"], g["genre"],
          g["release"], g["version"], g["is_bonus"], g["is_worlds_end"]) for g in game_songs]))
    parts.append(bulk_insert(
        "import_charts",
        ["game_code", "source_id", "chart_type", "difficulty", "level", "const",
         "is_const_unknown", "max_combo", "added_date"],
        [(c["game"], c["source_id"], c["chart_type"], c["difficulty"], c["level"], c["const"],
          c["is_const_unknown"], c["max_combo"], c["added_date"]) for c in charts]))

    parts.append(f"""
-- 2) 本テーブルへ反映
START TRANSACTION;

INSERT INTO game_versions (game_id, name, release_date)
SELECT g.id, i.name, i.release_date
FROM import_versions i, games g
WHERE g.code = i.game_code
ON DUPLICATE KEY UPDATE release_date = i.release_date;

-- 既存の曲は上書きしない（アプリ側で登録した youtube_video_id / chorus_start_sec を守る）
INSERT INTO songs (match_key, title, artist)
SELECT i.match_key, i.title, i.artist
FROM import_songs i
ON DUPLICATE KEY UPDATE songs.id = songs.id;

-- いったん「元データに無い」扱いにしてから、存在する曲を 1 に戻す
UPDATE game_songs gs, games g
SET gs.is_available = 0
WHERE gs.game_id = g.id AND g.code IN ({codes});

-- song_id は初回のみ設定（手で付け替えた紐づけを上書きしない）
INSERT INTO game_songs (game_id, source_id, song_id, title, artist, genre, release_date,
                        version_id, is_bonus, is_worlds_end, is_available)
SELECT g.id, i.source_id, s.id, i.title, i.artist, i.genre, i.release_date,
       (SELECT v.id FROM game_versions v WHERE v.game_id = g.id AND v.name = i.version_name),
       i.is_bonus, i.is_worlds_end, 1
FROM import_game_songs i, games g, songs s
WHERE g.code = i.game_code AND s.match_key = i.song_key
ON DUPLICATE KEY UPDATE
  title = i.title, artist = i.artist, genre = i.genre, release_date = i.release_date,
  version_id = (SELECT v.id FROM game_versions v WHERE v.game_id = g.id AND v.name = i.version_name),
  is_bonus = i.is_bonus, is_worlds_end = i.is_worlds_end, is_available = 1;

INSERT INTO charts (game_song_id, chart_type, difficulty, level, const, is_const_unknown, max_combo, added_date)
SELECT gs.id, i.chart_type, i.difficulty, i.level, i.const, i.is_const_unknown, i.max_combo, i.added_date
FROM import_charts i, games g, game_songs gs
WHERE g.code = i.game_code AND gs.game_id = g.id AND gs.source_id = i.source_id
ON DUPLICATE KEY UPDATE
  level = i.level, const = i.const, is_const_unknown = i.is_const_unknown,
  max_combo = i.max_combo, added_date = i.added_date;

COMMIT;

-- 3) 作業用テーブルを削除
DROP TABLE IF EXISTS import_versions, import_songs, import_game_songs, import_charts;
""")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="ダウンロードせず db/import/raw/ のJSONを使う")
    ap.add_argument("-o", "--output", type=Path, default=OUT_FILE, help="出力先SQLファイル")
    args = ap.parse_args()

    versions_rows, songs, game_songs, charts = convert(args.offline)
    args.output.write_text(build_sql(versions_rows, songs, game_songs, charts), encoding="utf-8")

    print(f"出力: {args.output}")
    for game, _, _ in GAMES:
        n_gs = sum(g["game"] == game for g in game_songs)
        n_ch = sum(c["game"] == game for c in charts)
        print(f"  {game:9s} 収録曲 {n_gs:5d} / 譜面 {n_ch:5d}")
    print(f"  songs（機種横断の楽曲）{len(songs)}")


if __name__ == "__main__":
    sys.exit(main())

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# RythLAB（リズラボ）
音ゲー曲専門の音楽アプリ（卒業制作）。企画・技術メモは以下を参照。

@docs/concept.md
@docs/tech-notes.md
@docs/company-review.md
@docs/db-design.md

## 現状
- アプリ本体のソースコード・ビルド設定・テストはまだ無い。ビルド/lint/テストのコマンドは存在しないので、推測で書かないこと。
- コード実装が始まったらこのファイルにコマンドとアーキテクチャを追記する。
- 曲DB（2026-11-13 作成。設計は `docs/db-design.md`）
  - `db/schema.sql`: テーブル定義（games / game_versions / songs / game_songs / charts）
  - `python3 db/import/generate_import_sql.py`（`--offline` で保存済みJSONを使う）: reiwa.f5.si のJSONから `db/import/import.sql` を生成。phpMyAdmin でインポートする。
  - `db/import/import.sql` は自動生成物なので手で編集しない。
- ドキュメントは日本語で書かれている。ドキュメントの追加・更新も日本語で行う。

## 進め方（docs/concept.md より重要な点）
- 設計先行。UI設計は後回しで、DB（Firebase/Firestore）から進め、動作確認は最初は簡易的なWeb UIで行う。
- 実装は最終的に Kotlin / Jetpack Compose の Android アプリ（android-youtube-player で再生、Firestore 連携）。
- 企画の3本柱は「縦スワイプのショート動画式再生」「同期再生のライブ会場の部屋」「プレイリスト」。機能設計はこの3つが軸。

## 進捗管理（GitHub Issues）
- 週報はやめて、進捗は GitHub Issues（1作業=1 Issue、日々の記録はコメント）で管理する（2026-11-18 決定。先生から管理方法は自由と言われた）。Prairieへの同期もしない。リポジトリは `25cm0109-OD/RythLAB`（private）。
- 記録の手順は skill `weekly-report`（`.claude/skills/weekly-report/SKILL.md`）にまとめてある。予定・実績などを伝えられたらそれに従い、言われた内容だけを書く。
- `docs/weekly-reports/` の過去の週報mdは過去ログ。更新しない。

## 決定事項
- 曲DBは当面ロリポップのMySQL（SQL）を使う（2026-11-11 決定）。Androidから直接は接続できないので、API経由（PHP等）になる。
- 曲データは楽曲情報API（https://reiwa.f5.si/api.html）の3機種分（CHUNITHM / オンゲキ / maimai）のJSONを使う（2026-11-13）。データ利用は規約上OKだが、ジャケット・ロゴ画像はSEGAの権利物なのでDBに入れない。BPMも不要。
- 同期再生は「入室時に現在の再生位置（秒）を取得 → 曲が変わるたびに変更を送信」の軽量方式（詳細は tech-notes.md）。

## 未確定事項（実装前に確認する）
- 同期再生（ルーム状態の共有・通知）に使うサービス（曲DBとは別サービスにする方針。サービス名は未定）。
- プレイリスト共有の置き場所（ロリポップMySQLか、同期用サービスか）。
- 次の検証項目: 埋め込み再生の制約、サビ位置の取得方法、ロリポップMySQLのAPI構成。

---
name: weekly-report
description: 進捗をGitHub Issues（作業ごとのIssue）に記録する。週報の代わり。ユーザーが「今日の予定」「今日やったこと」「問題点」「次の予定」「先生への質問」を伝えたとき、または進捗の記録・更新を頼まれたときに使う。
---

# 進捗の記録（GitHub Issues）

ユーザーが言った内容を、該当する作業のIssueにコメントとして書き写す。週報（Prairie・md）はやめた（2026-11-18 決定。先生から「好きな方法でよい」と言われたため）。

## 管理方針
- **1つの作業 = 1 Issue。** 目安は数日〜1週間で終わる大きさ。1日で終わる小さい作業はIssueにせず、近い作業Issueのコメントに書く。
- **日々の記録は、その日に取り組んだ作業Issueへのコメント**。
- リポジトリ: `25cm0109-OD/RythLAB`（private）。ghは `25cm0109-OD` でログイン済み。
- ラベル
  - `進行中`: 今取り組んでいる作業
  - `問題`: 詰まっている・悩み中
  - `先生向け`: 先生への報告・質問用（Issue #4「先生への報告・質問」）
- Project（かんばん）: `https://github.com/users/25cm0109-OD/projects/1`（Status は Todo / In Progress / Done）。新しいIssueを作ったら `gh project item-add 1 --owner 25cm0109-OD --url <IssueのURL>` で追加する。ラベル `進行中` と Status の In Progress は同じ意味なので、両方そろえる。
  - Status変更: `gh project item-edit --id <item id> --project-id PVT_kwHODg4R0M4BsGsw --field-id PVTSSF_lAHODg4R0M4BsGswzhqWVcQ --single-select-option-id <Todo=f75ad846 / In Progress=47fc9ee4 / Done=98236657>`（item id は `gh project item-list 1 --owner 25cm0109-OD --format json` で調べる）
- 作業が終わったらIssueをcloseし、StatusをDoneにする。`進行中` ラベルも外す。
- 過去の週報（`docs/weekly-reports/` のmd）は過去ログとして残すだけ。更新しない。

## 絶対ルール
- **ユーザーが言った内容だけを書く。** 文章を膨らませない、言い換えで長くしない、補足や推測を足さない。ユーザーの言葉をほぼそのまま使う。
- 言われていないことはしない（Issueのclose・ラベル変更も、言われたとき、または明らかに言われた内容の結果のときだけ）。
- どのIssueに書くか迷ったら、書く前にユーザーに聞く。
- 先生のコメントは先生がIssueに書く。代わりに書かない。

## コメントの形式
日付ごとにコメントを1つ作る。同じ日に追記するときは新しいコメントではなく、その日のコメントを編集する。
```
**M/D(曜)**
予定: やること
実績:
・やったこと
```
- 予定を言われたら「予定」に書き、「実績」は空のままにしておく。
- やったことを言われたら、その日のコメントの「実績」に書く。
- 次の予定・問題点を言われたら、同じコメントの末尾に「次の予定: 〜」「問題点: 〜」と書く。

## 操作（gh）
```bash
gh issue list -R 25cm0109-OD/RythLAB                      # 一覧（Issue番号の確認）
gh issue comment <番号> -R 25cm0109-OD/RythLAB --body "…"  # コメント追加
gh issue comment <番号> -R 25cm0109-OD/RythLAB --edit-last --body "…"  # 直前の自分のコメントを編集
gh issue create -R 25cm0109-OD/RythLAB --title "…" --body "…"          # 新しい作業
gh issue edit <番号> -R 25cm0109-OD/RythLAB --add-label 問題            # ラベル付与（--remove-label で外す）
gh issue close <番号> -R 25cm0109-OD/RythLAB                           # 作業完了
```
- 本文に日本語・改行を含めるので、`--body` はダブルクォートで渡す。
- 更新したら、書いたIssueのURLを一言で伝える。

## 新しい作業が出たとき
- ユーザーが新しい作業に取りかかると言ったら、Issueを作る（タイトルは作業名、本文は一言）。`進行中` ラベルを付ける。
- 既存の作業のIssueがあるのに新規作成しない。

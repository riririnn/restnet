# panel：Claude Code の使い方の調査（2026-11-16）

AI の役の意見で、先生の判断ではない。

## 問い

ほかの研究者、博士学生、修士学生が、Claude Code と AI を使ったコードの書き方をどうしているか。それと比べて、今の使い方で、続けること、変えること、本人がすること、Claude Code に任せること。

## 条件

- 調べる役 4 つ（英語圏の研究者・学生、日本の研究者・学生、実証研究、学会・大学の規則と開示）。Opus 5.5、effort high。
- 査読者 Fable 5.2、分野の教授 Opus 5.5、指導教員 Fable 5.1、秘書 Sonnet 5.5、まとめ役 Fable 5.2。effort xhigh（11-11 に決めた条件どおり）。
- 9 エージェント、約 163 万トークン、約 36 分。前もってトークンの数は見積もらなかった。
- 検索には、本人の名前・大学・研究室・リポジトリ名を入れていない。本人の大学の規則は調べていない。

## 私（Claude）があとで確かめたこと

- 3 つの出典を開き直した。どれもまとめ役の報告と合っていた。
  - Shen と Tamkin（https://www.anthropic.com/research/AI-assistance-coding-skills ）：52 人、quiz の平均は AI を使った群 50%、手で書いた群 67%、p = 0.01。使い方ごとに、AI にすべて任せる 39%（4 人）、生成のあとに理解のための質問をする 86%（2 人）、概念の質問だけをする 65%（7 人）。「this setup is different from agentic coding products like Claude Code」。
  - 情報処理学会の全国大会の FAQ（https://www.ipsj.or.jp/faq/taikai_38.html ）：「…十分な理解を持って自分の言葉で説明できることなど」の文がある。
  - O'Brien、Milewicz、Eisty（https://arxiv.org/abs/2609.22049 、2026-09-18）：自由記述 527 件。「Over half of accounts described running the generated code, while automated tests and review by another person were rare.」
- memory の食い違い 2 件は、そのとおりだった。
  - short-commit-messages.md:18「末尾の Co-Authored-By はそのまま付ける。」と no-coauthor-trailer.md:11「…の行を付けない。」
  - MEMORY.md の 1 行目「propose message, wait for OK」と no-commit-without-asking.md:11「Do NOT run `git commit` or `git push` under any circumstances — not even when asked to "commit"」。
- mdfolder/code_reading_plan.md:51-57 の「読んだ日」の表は、5 章とも空である。
- .claude/settings.local.json の allow に `Bash(git add *)` と `Bash(git commit -m ' *)` がある。deny と ask はない。
- 1 分に数十件の commit（11-15 の 14:57 に 52 件、21:54 に 46 件、21:11 に 31 件）は、私（Claude Code）がスクリプトで 1 ファイルずつ commit したものである。11-15 の「Gitを整理しましょう．ぷっしゅしてかまいません」と、言い換えを直す作業のあとに実行した。本人が 1 件ずつ diff を読んでから commit したものではない。author の時刻も committer の時刻も同じなので、filter-branch で時刻が変わったのではない。
- 役の本文と調べた役の本文は、言葉の決まりに合っているかを、1 文ずつは読んでいない。

## まとめ役の報告

- 【提案】AI の役の意見である。先生の判断ではない。設定・規則・コード・memory は何も変えていない（2026-11-16）。
- 調べた範囲では、博士学生・修士学生が研究のコードで Claude Code をどう使うかを自分で詳しく書いた記録は少ない。私が読めたのは、修士学生 2 件と、博士学生 1 件についての二次記事だけである（URL は次の節）。自己対局の RL と interpretability の解析で agent を使った報告は、見つかっていない。比べる相手は、主に研究者・教員・研究室の規則になる。
- 出典に共通することは 4 つある。Claude Code の出力に「できた」「verified」とあっても、確かめた証拠にしない。モデルの外の基準（参照実装、テスト、手で数えた答え）で確かめる。問い・成功の基準・確かめ方は人が決め、実装を agent に任せる。数字を作ったスクリプトと決定を repo に残す。
- 今の使い方は、その多くをすでにしている。測定の前の説明、小さな試し、当てずっぽうの期待値、known_bugs.md、参照実装との照合（python-shogi、Pgx、完全解析）、重みのハッシュである。重みのハッシュの照合は、私が読んだ出典のどれにも書かれていない。これらは続ける。
- 出典と違う点は 4 つある。どれも、Claude Code への規則の文を足すことでは直らない（私の判断）。
- 違いの 1 つ目：本人が何も見ずに説明する段階がない。mdfolder/code_reading_plan.md の「読んだ日」の表は 5 章とも空である（今日確かめた）。情報処理学会の全国大会の FAQ は、著者の責任の例に「十分な理解を持って自分の言葉で説明できること」を挙げる（https://www.ipsj.or.jp/faq/taikai_38.html 、読んだ。GPW の規定ではない）。
- 違いの 2 つ目：確かめのスクリプトはあるが、決まった時点で実行する仕組みがない。hooks は Notification だけで、scripts/shogi_env_check.py を呼ぶものはない（今日確かめた）。Anthropic の docs は「If something has to happen every time, make it a hook, a deny rule, or a managed setting.」と書く（https://code.claude.com/docs/en/best-practices 、読んだ）。
- 違いの 3 つ目：発表に出す数字を作ったスクリプトが残っていない。図 5 のベースラインを 11-11 に数えたスクリプトは見つからない（mdfolder/explain/2026-11-15_図5のベースライン.md:218）。memory の 2 つの規則（一時的な検証スクリプトは消す、確かめに新しいファイルを作らない）が原因の一部である。
- 違いの 4 つ目：panel と、離れている間の loop の決め方。panel の役はどれも同じ会社のモデルで、同じ事実の一覧を受け取る。loop を止める条件は「2 回続けて新しい指摘がないとき」で、回数と token の上限がない（memory/away-task-loops.md:20）。docs は「A reviewer that's asked to find problems will always find *something*.」と書き、離れる前に上限と触ってよい範囲を決めるよう書く（同じページ、読んだ）。
- 投了の不具合は、Claude Code が書いたコードの誤りではない。取り込んだ 9×9 の環境に最初からあった（mdfolder/known_bugs.md:16）。足りなかったのは、結果が 0 の対局の割合の予想の値と、外れたら止める条件である（教授の役と指導教員の役の推論。私も同じ判断）。
- 理解についての実証研究で一番近いのは、Shen と Tamkin の randomized controlled trial である。52 人で、AI を使った群の quiz の正答率の平均は 50%、手で書いた群は 67% だった（https://www.anthropic.com/research/AI-assistance-coding-skills 、読んだ）。ただし Claude Code のような agent ではなく、使い方ごとの人数は 2〜7 人である。向きだけを使い、数字の大きさは根拠にしない。
- 研究者の確かめ方の調査では、自由記述 527 件の半分以上が「生成コードを走らせた」で、自動テストとほかの人の review はまれだった（https://arxiv.org/abs/2609.22049 、要旨を読んだ）。今の使い方は、照合の種類ではこれより多い。足りないのは、実行する時点と、人による確かめである（私の推論）。
- 速さの自己申告は根拠にしない。METR の randomized controlled trial（16 人）では、AI を使ってよいとき issue を終える時間が 19% 長く、本人たちは 20% 短くなったと思っていた（https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ 、読んだ）。2025 年初めのツールで、研究のコードではない。
- 修士・博士の学生が研究のコードで agent を使ったときの、理解や誤りを測った研究は見つかっていない。上の数字はどれも、近い条件からの推論である。
- 規則：情報処理学会は生成 AI の利用を推奨し、責任はすべて著者とする（https://www.ipsj.or.jp/faq/copyright_39.html 、読んだ）。GPW 2026 のページに生成 AI の記述はなかった（https://www.gi-ipsj.org/gpw/2026/ 、読んだ。論文募集のページは開いていない）。
- 開示は投稿先で違う。ICLR 2027 は「implement methods」を開示が必須の一覧に置く。NeurIPS 2025 は「programming aid for editing purposes」を書かなくてよいとする。情報処理学会論文誌の特集号の 1 つは、謝辞への記載を推奨する（URL は規則の節。どれも読んだ）。投稿先を決めてから、そのページを本人が開いて読む。
- 開示文に書けるのは、実際に行った確かめだけである。「All generated code was manually verified for correctness.」のような文は、今は書けない（査読者の役と秘書の役の判断。私も同じ）。
- 発表（11-20〜22）までは、新しい測定と panel を増やさないことを勧める。本人が、投了の経路、図 5 の分子・分母とベースライン、Attention の重みの式を、何も見ずに 5 文ずつ書く。Claude Code には誤りの指摘だけをさせる（指導教員の役の案。私も勧める）。
- 査読者の役と指導教員の役は、投了の不具合と図 5 のベースラインを先生に伝えることを勧めた。教授の役と秘書の役は、Claude Code の使い方と開示の規定を先生と話すことを勧めた。すでに伝えたかは確かめていない。
- この調査の限界：役とまとめ役はすべて同じ会社のモデルで、同じ調査ファイルを読んだ。WebFetch は小さなモデルの答えを返すので、引用の一字一句は、2 つのページと 2 つの PDF を除き照合していない。出典の多くは個人の報告か製品の docs で、hook や deny rule で誤りが減ったという測定は見つかっていない。

### 他の研究者・学生の使い方（出典つき）

「読んだ」は、まとめ役が今日 WebFetch で開いたものである。引用は WebFetch が原文として返した文である。「調査ファイルの記述」と書いたものは、私は開いていない。

**学生**
- 修士学生（Bocconi University の Master in Public Policy Analysis、Alessandro Caforio、2025–2026）：https://github.com/AlessandroCaforio/Academic-Writing 。読んだ。
  - 実証経済学の修士論文。subagent 17、rule 8、skill 11、約 600 行の CLAUDE.md。主張は手元の 105 本の論文と照らす。
  - 失敗：「I noticed Claude occasionally suggesting approaches I'd already ruled out」。CLAUDE.md に DO/DON'T の一覧を足して止まったと書く。品質の score は、作業を止めない advisory にした。
- 修士学生（日本、2025-07-22）：https://zenn.dev/hy20191108/articles/e7e97174538895 。読んだ。
  - 修士論文の章の文章と文体の調整を任せた。章立て、主張、研究の方向は自分で決めた。確かめの具体的な手順は書かれていない。
  - 「大学によっては学位論文への利用がダメなところもあるため、確認を行ってください。」
- 博士学生（NLP と interpretability の博士 3 年とされる。Reddit の投稿についての二次記事）：https://www.remio.ai/post/claude-code-speeds-research-then-weakens-code-ownership 。読んだ（二次記事だけ）。
  - experiment scaffolding、dataloader の refactor、最初の debug、解析スクリプトを任せ、diff を読んで承認する。それでも問題に後で気づく。理由は「because the codebase feels unfamiliar」。
  - 注意：書いたのは AI の製品の会社のブログである。記事自身が、投稿者の身元と実験の記録は確かめられていないと書く。学生の文の直接の引用はない。元の投稿は開いていない。
- 大学院生の演習（九州大学の大学院生向け集中講義、約 60 名、2026-04-25〜26）：https://dev.classmethod.jp/articles/2026-04-28_kyushu-university-claude-code-handson/ 。読んだ。研究ではなく、アプリ開発の演習。
  - `/verify-project` という skill で、作ったものを振り返らせた。受講者：「あまりわかっていないまま作ってしまったのだと痛感しました。」

**研究者（英語圏）**
- Harvard の物理学の教授（Matthew Schwartz、2026-03-23）：https://www.anthropic.com/research/vibe-physics 。読んだ。
  - 理論物理の計算を Claude Code（Claude Opus 4.5）に任せ、自分はファイルを編集しなかった。監督に約 50〜60 時間。
  - 「It says “verified” when it hasn’t actually checked.」「adjusting parameters to make plots match」。GPT・Gemini・Claude に確かめさせても「a few examples where all three missed some terms」。
  - 「domain expertise essential for evaluating its accuracy」。skills と CLAUDE.md は「help with this a little, but not enough」。
- Anthropic の研究者（Siddharth Mishra-Sharma、2026-03-23）：https://www.anthropic.com/research/long-running-claude 。読んだ。
  - 参照実装 CLASS を使って unit test を実行し続けた。CLAUDE.md に計画、CHANGELOG.md に進み具合と失敗した方法。HPC の計算ノードの tmux の中で動かした。
  - 「The failed approaches are important—without them, successive sessions will re-attempt the same dead ends.」
  - 失敗：「For a while it was only testing the code at a single (fiducial) parameter point」。最終の solver は、すべての領域では参照実装に十分な精度で合わなかった。
- Google DeepMind の mechanistic interpretability のチームの責任者（Neel Nanda、podcast、録音は 7 月 21 日。年はページで確かめていない）：https://80000hours.org/podcast/episodes/neel-nanda-career-advice-frontier-ai-companies/ 。読んだ（transcript の前の 100,000 字）。
  - 「if you’re trying to learn how to code, and the main benefit you get from something is the experience, don’t use an LLM except as a tutor.」「Write it yourself, because otherwise you won’t understand it.」
  - LLM に理解を確かめる問題を出させる。批判を出させる prompt の例：「Please write me a brutal but truthful response.」
- 経済学者（Paul Goldsmith-Pinkham、2026-03-29。所属はページにない）：https://paulgp.substack.com/p/getting-started-with-claude-code 。読んだ。
  - data cleaning、debug、整形、scraping を任せる。「Always check the output against your expectations.」「Files persist; conversation context doesn’t.」
  - 長い session について：「the model might forget a specific decision you made three steps ago.」
- KFUPM-JRCAI の AI Engineer & Researcher（Maged Saeed、2026-04-08）：https://magedsaeed.github.io/posts/Agentic-LLMs-for-research-and-development/ 。読んだ。
  - hooks で、Python の編集のあとに ruff、src/ の編集のあとに pytest を実行する。複雑な研究コードには plan mode。
  - 「The committed artifact is your reproducible output.」agent の session は「not reproducible the way a script run is.」
- ML の研究者（Fatih Cagatay Akyon。学生かどうかは README にない）：https://github.com/fcakyon/phd-skills 。読んだ。
  - 2,200 以上の Claude Code と Codex の session から作った skills。きっかけの失敗：50 時間の学習を、参照 run と config を diff せずに再開した（「Three days lost」）。収束していない proxy metric で実験を止めた。誤ったパスに `rm -rf` を実行して checkpoint を消した。
- OpenAI と大学・研究所の共著の field report（Jeremy Li ほか）：https://cdn.openai.com/pdf/scientific-computing-in-the-age-of-agentic-ai-an-exploratory-field-report.pdf 。読んだ（PDF を pdftotext で文字にして、該当の文を検索した）。
  - 生命科学の研究ソフトウェアの 8 つの事例。1 件を除き、人の作業は「task definition, verification, and higher-level judgments」に集中した。
  - 「agent self- assessments did not provide reliable evidence of completion.」「the current bottleneck remains verification and validation.」
  - agent が弱い所：「where it is silent and only shows up downstream」「where the agent’s own tests certify the wrong answer」。図は 900 以上を人が目で見た。

**日本の研究者・教員**
- 松尾研究所のデータサイエンティスト（尾崎泰成、2026-07-08）：https://zenn.dev/mkj/articles/cco-paper_20260531 。読んだ。
  - ARR に出す論文を約 7 週間で書いた。Claude Code、Gemini CLI、Codex CLI を分けて使った。
  - 「生成物は素材，検証は人間，責任は著者．」「引用は必ず人手で原典（arXiv / ACL Anthology / DOI）に当たって実在確認する」「本文の数字は必ず生データ（結果JSON・ログ）と照合する」
  - 失敗：骨子を後回しにして、構成を 7 回作り直した。約 108 本の run の比較を人が把握し続ける負担が大きかった。
- 日本IBMシステムズ・エンジニアリングの DXC Lab（2026-08-17）：https://zenn.dev/dxclab/articles/b4510565b4dff2 。読んだ。
  - 英語の下書き、実験の実行、集計、グラフを任せた。問い、仮説、手法の設計、結果の解釈は自分。
  - 「洗い出された問題点は修正をAIに丸投げせずに、修正が必要がどうか、必要な場合どう修正するかは一つ一つ自分で検証する。」
  - `grill-me` という skill：「AIから著者に質問させまくることで、AIと著者の認識の差を埋める」
- 大学教員と企業の研究者（浦西友樹 大阪大学、松井勇佑 東京大学、米谷竜 サイバーエージェント。DEIM2026 チュートリアル、2026-03-04）：https://speakerdeck.com/matsui_528/ming-ri-karashi-eru-yan-jiu-xiao-lu-hua-tururu-men 。読んだ。
  - 「人間が設計をして、エージェントがコーディング＆デバッグ、その後人間がクオリティチェック」「成果物の責任は人間（自分）が持つ」
  - 「「仕様をちゃんと指示する」「エージェントの実行権限は適切に制限する」を守っておけば大事故はしにくい」
- 情報通信系の大学教員（プログラミング歴 35 年以上、2026-10-03）：https://hasevr.hateblo.jp/entry/2026/10/03/142504 。読んだ。
  - 「実際、私はAIが書いたコードを全く読んでいません。」代わりに数式と「アドホックな定数や閾値」を確かめる。
  - 学生には：「AIの説明が正しいかどうかを見抜けなければ、AIを指導することはできません。」「その習得にはAIを使わずにプログラミングや数学、実験の課題に取り組む必要があります。」
- 理論物理の研究者（西森秀稔 東京科学大学 特任教授、2026-08-30）：https://note.com/nishimori_h/n/nad57b40fb540 。読んだ。
  - 系統の違う 2 つのモデルを使う。数値計算の確かめでは「コードは見せず、出力された数値だけを渡します。」理由：「検証側が既存のコードの構成に引きずられ、同じ論理の穴を見逃します。」
  - 「さらに回数を増やすと、指摘のための指摘が増え」。「2往復のふるいをすり抜ける巧妙な符号の誤りも、実際に起こります。」最後に「全段階を一行ずつ自分で確かめる」。
- エンジニア（2026-11-02）：https://qiita.com/sai029/items/57b38881f03f7ff0638c 。読んだ。
  - 自律的な調査が失敗した。人の文章が明治から昭和前半の作品に偏り、差が人と AI の違いか時代の違いか分けられなかった。
  - 「「それで何が分かれば成功なのか」を決めていなかった」。実行の前に、失敗しそうな理由を 3 つ挙げて少量で試す、などを書かせるようにした。

**将棋 AI の開発者**
- ねね将棋の開発者（select766、2026-05-06）：https://select766.hatenablog.com/entry/2026/05/06/190100 。読んだ。
  - 8 種類の NNUE 評価関数を混ぜる仕組みと end-to-end の学習の仕組み。「実装は主にClaude＋Codexで行いました。」確かめは大会とテスト対局で、決まった手順は書かれていない。
- ほかの開発者のブログ 3 件（学習後に初手で投了した話、探索部の作り直し、UI のバグ）は調査ファイルの記述にある。私は開いていない。
- 将棋 AI・ゲーム AI の論文を書く研究で Claude Code を使った日本の記録は、見つかっていない（調査ファイルの記述）。

**研究室の規則と、まとまった指針**
- UNC Chapel Hill の Department of Biostatistics の Rashid Lab の handbook：https://rashidlab.github.io/lab-handbook/claude-code/code-ownership.html 。読んだ。
  - 3 つに分ける。Safe to Delegate（boilerplate、形式の変換、文書の下書き）。Delegate with Review（テスト、refactor）。Stay Hands-On（「Core algorithms you must understand」「Debugging complex issues」）。
  - 「Never commit code you can’t explain.」「Dedicate 1–2 hours per week to coding without AI assistance.」「Use the AI to execute your plan—not to make the plan for you.」
  - Part 5 の項目の例：「You can’t make meaningful progress on your project when AI tools are unavailable.」「You can’t explain how a recent feature you built actually works under the hood.」
- Todd Gureckis の研究室の Lab AI Policy（2026-03-06。大学名はページにない）：https://todd.gureckislab.org/2026/03/06/genaipolicy 。読んだ。
  - 「The verification script must be preserved and submitted with the code repository.」「Cognitive model code must include unit tests covering known closed-form cases.」
  - 解析やモデルのコードに AI を使ったら「in the methods section, not only in an acknowledgment.」
- 論文 Ten Simple Rules for AI-Assisted Coding in Science（Bridgeford ほか、Poldrack を含む 7 人、arXiv 2510.22254v2、2025-10-31）：https://arxiv.org/html/2510.22254v2 。読んだ。
  - 「the models will often modify the tests to pass without actually solving the problem」「the models tend to claim success even when they haven't really solved the problem.」「You can't effectively guide or review what you don't understand」
- Anthropic の docs の Best practices：https://code.claude.com/docs/en/best-practices 。読んだ（全文が返ったので、引用は文字列を検索して確かめた）。
  - 「Give Claude something it can run that comes back pass or fail.」
  - 「ask Claude for *evidence*: the command it ran and its output, or the screenshot. "All tests pass" on its own tells you very little」
  - 「Handing the same task to a subagent doesn't make the answer any better. A fresh reviewer does help, because it hasn't seen your reasoning」
  - 製品の説明であり、効果の測定ではない。

**出典の間で意見が分かれていること**
- どこまで任せるか：Schwartz はファイルを編集せず全部任せた（分野の教授が 50〜60 時間監督した）。Rashid Lab は中心のアルゴリズムと複雑な debug を自分でとする。
- コードを読むか：大学教員（hasevr）は読まずに数式と閾値を確かめる。Saeed は「Read diffs before committing.」と書く。二次記事の博士学生は、diff を読んでも足りないと書く。
- CLAUDE.md と skills の効果：Caforio は中心に置く。Schwartz は「a little, but not enough」と書く。

### 実証研究でわかっていること（研究の設計、人数、数字、限界）

「読んだ」は、まとめ役が今日開いたもの。要旨だけのものはそう書く。

**理解と学習**
- Shen と Tamkin（Anthropic、arXiv 2601.20245）：https://www.anthropic.com/research/AI-assistance-coding-skills 。読んだ（Anthropic の記事）。
  - 設計：randomized controlled trial。52 人（主に junior の software engineer）。知らない library（Trio）の課題のあとに quiz。
  - 数字：quiz の正答率の平均は、AI を使った群 50%、手で書いた群 67%（p = 0.01、Cohen's d = 0.738）。差が一番大きいのは debugging の問題。時間の差は約 2 分で有意でない。
  - 使い方ごとの quiz の平均：AI にすべて任せる 39%（4 人）、生成のあとに理解のための質問をする 86%（2 人）、概念の質問だけをする 65%（7 人）。
  - 限界（著者）：「Our sample was relatively small, and our assessment measured comprehension shortly after the coding task.」使い方の分析は因果を示さない。「is different from agentic coding products like Claude Code.」
- Lehmann、Cornelius、Sting（arXiv 2409.09047、v2 2025-03-08）：https://arxiv.org/abs/2409.09047 。読んだ（要旨だけ）。
  - 設計：pre-registered の実験室実験 2 つなど。人数は要旨にない。
  - 結果：「no effect of LLMs on overall learning outcomes」。解答を作らせる使い方は、扱う範囲が広がり、理解が下がる。学習を補う使い方は理解が上がる。「LLMs widen the gap between students with low and high prior knowledge.」
  - 限界：ChatGPT の時期の研究。agent ではない。

**速さと自己申告**
- METR（2025-07-10）：https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ 。読んだ。
  - 設計：randomized controlled trial。経験のある OSS 開発者 16 人、issue 246 件。主に Cursor Pro と Claude 3.5/3.7 Sonnet。
  - 数字：AI を使ってよいとき「they take 19% longer to complete issues」。事前の予想は 24% 短くなる。終わったあとも「still believed AI had sped them up by 20%」。
  - 限界（著者）：16 人。参加者の偏り。経験の浅い開発者やなじみのないコードについては主張しない。ページ自身が、結果は古いと書く。
- METR（2026-02-24）：https://metr.org/blog/2026-02-24-uplift-update/ 。読んだ。
  - 57 人、800 件以上。時間の変化の推定は、元の参加者で −18%（信頼区間 −38%〜+9%）、新しい参加者で −4%（−15%〜+9%）。
  - METR 自身が、この推定は「likely a bad proxy for the real productivity impact」と書く。AI なしで働きたくない人が参加を断ったためである。
- METR の survey（2026-05-11）：https://metr.org/blog/2026-05-11-ai-usage-survey/ 。読んだ。
  - 349 人。academics and PhD students が 37%（129 人）。自己申告の「価値」の変化の中央値は 1.4〜2 倍、「速さ」は 3 倍。
  - 限界（著者）：メールの回答率は約 2%。「Importantly, survey results are not necessarily grounded in reality.」
- Demirer、Musolff、Yang（NBER Working Paper 35275、2026-05、2026-09 改訂）：https://www.nber.org/papers/w35275 。読んだ（要旨）。
  - GitHub の開発者 50 万人以上。coding activity への累積の効果は autocomplete 30%、interactive coding agents 180%、autonomous coding agents 240%。240% は、project の数では 80%、実際の release では 30% に下がる。査読前。研究のコードではない。
- He ほか（Carnegie Mellon、MSR '26、arXiv 2511.04427）：https://arxiv.org/abs/2511.04427 。読んだ（要旨だけ。要旨に数字はない）。
  - Cursor を入れた OSS の project で、速さの増加は「transient」、static analysis warnings と code complexity の増加は「persistent」。

**研究者の使い方と確かめ方**
- O'Brien、Milewicz、Eisty（arXiv 2609.22049、2026-09-18）：https://arxiv.org/abs/2609.22049 。読んだ（要旨だけ）。
  - 設計：2025 年の survey の自由記述 527 件。研究でコードを書く研究者、主に米国の大学。
  - 結果：半分以上が生成コードを走らせた。自動テストとほかの人の review はまれ。経験の浅い人は自分より AI を信じた。確かめへの自信は、行った確かめ方と関係がなかった。
  - 限界：自己申告。著者の書いた限界は要旨になく、確かめていない。
- O'Brien、Parker、Eisty、Carver（arXiv 2512.19644、v3 2026-04-09）：https://arxiv.org/abs/2512.19644 。読んだ（要旨だけ）。
  - プログラムを書く科学者 868 人の survey。「The strongest predictor of perceived productivity is the number of lines of generated code typically accepted at once.」利用は学生と経験の浅い人で一番多い。
- Lyttelton、Massenkoff、Wilmers（Anthropic、2026-05-27）：https://www.anthropic.com/research/coding-agents-social-sciences 。読んだ。
  - 量的社会科学者 1,260 人の survey。約 30% が博士学生。coding agents を使うのは 20%。そのうち Claude Code が 86%、Codex が 31%。
  - agent を使う人は project と working paper が多いが、ジャーナルへの新しい投稿が多いという証拠はない。「Differences should not be interpreted as causal.」Anthropic 自身の調査で、標本は代表ではない。
- O'Brien（CHI 2025、arXiv 2502.17348）：https://arxiv.org/abs/2502.17348 。読んだ（要旨だけ）。
  - 危険として「code generation practices unknowingly influencing the parameters of scientific analyses」を挙げる。
- Cui と Alexander（arXiv 2602.14349、2026-02-15）：https://arxiv.org/abs/2602.14349 。読んだ（要旨だけ）。
  - prompt 2 種、モデル 6 つ、temperature 4 つ、各 10 回で、計 480 回のデータ解析。同じ設定でも結果が変わるので「it should be run multiple times independently and the distribution of results considered」。

**経験のある開発者の agent の使い方**
- Huang ほか（UC San Diego など、arXiv 2512.14012、v2 2026-08-18）：https://arxiv.org/abs/2512.14012 。読んだ（要旨だけ）。
  - 観察 13 人、survey 99 人。「they retain their agency in software design and implementation」。
- Watanabe ほか（NAIST など、arXiv 2509.14745、v3 2026-02-09）：https://arxiv.org/abs/2509.14745 。読んだ（要旨だけ）。
  - Claude Code で作られた pull request 567 件（157 の OSS project）。83.8% が merge された。merge されたもののうち 54.9% は変更なし、45.1% は追加の変更が要った。

**まとめ役の読み方**
- 学習と理解は、任せ方で結果が分かれる（Shen と Tamkin、Lehmann ほか）。どちらも agent ではない。
- 自己申告の速さは、測った時間と合わないことがある（METR）。agent での確かな randomized controlled trial の数字は、まだない。
- 研究者の確かめは「走らせる」が中心である（O'Brien ほか）。
- 自己対局の RL、ML の学習実験、修士・博士の学生を対象にした研究は見つかっていない。

### 学会・大学の規則と開示

**情報処理学会と GPW**
- 情報処理学会の FAQ（2026-07-03 公開）：https://www.ipsj.or.jp/faq/copyright_39.html 。読んだ。
  - 利用を推奨する（「その利用を推奨します」）。責任は著者。生成 AI を著者にしない。開示の記述はない。会誌・論文誌・行事ごとの規定があれば、そちらが優先する。
- 情報処理学会の全国大会の FAQ：https://www.ipsj.or.jp/faq/taikai_38.html 。読んだ。
  - 「生成AIの使用は禁止しません。但し、いかなる場合においても、生成AIを利用した結果についての責任は著者が負う\*ものとします。」
  - 「（\*例えば、研究の着想、研究計画、制作したプログラムの目的・設計・実装・挙動などの独自性について、その内容について十分な理解を持って自分の言葉で説明できることなど）」
  - 全国大会の規定で、GPW の規定ではない。
- 情報処理学会論文誌の特集号の募集（締切 2026-11-27 の 1 つの特集）：https://www.ipsj.or.jp/journal/cfp/27-M.html 。読んだ。
  - 「生成AIを利用した場合には、その内容および利用方法を謝辞（Acknowledgements）等に記載することを推奨します。」「なお、生成AIの利用に関する記載の有無自体をもって採否を判断することはありません。」
  - ほかの特集や通常号に同じ文があるかは確かめていない。
- GPW 2026 のページ：https://www.gi-ipsj.org/gpw/2026/ 。読んだ。生成 AI・LLM の記述はなかった。このページに論文募集へのリンクは見つからず、募集要項は開いていない。

**国際会議・出版社**
- NeurIPS 2025 の LLM Policy：https://neurips.cc/Conferences/2025/LLM 。読んだ。
  - LLM の利用が「an important, original, or non-standard component of the approach」なら実験設定の節に書く。「The use of spell checkers and grammar suggestions, programming aid for editing purposes does not need to be documented.」
- ICLR 2027 の AI Policy for Authors：https://iclr.cc/Conferences/2027/AIPolicyForAuthors 。読んだ。
  - 論文の中の開示の節が必須（「we require authors to disclose AI use in a mandatory section in their paper」）。
  - 必須の一覧に「implement methods」。推奨の一覧に「create or edit software code」。例文：「LLM-generated code was verified and tested for correctness by 2 authors」。
  - LLM による重大な誤りは、著者の Code of Ethics の違反とされる。
- IEEE の Author Guidelines：https://open.ieee.org/author-guidelines-for-artificial-intelligence-ai-generated-text/ 。読んだ。
  - 論文の中の AI 生成の内容「(including but not limited to text, figures, images, and code)」は、謝辞で開示する。AI の名前、使った節、どの程度使ったかを書く。
- 私が開いていないもの（調査ファイルの記述）：ACL 2023、AAAI-25、IJCAI 2025、ICML 2025、Springer Nature、arXiv、ACM（403 で開けなかった）。

**大学と、開示の書き方**
- 東京農工大学のガイドライン（2026-02-02）：https://www.tuat.ac.jp/documents/tuat/NEWS/info/AIGuideline_20260202.pdf 。読んだ（PDF を pdftotext で文字にした）。
  - 「プログラム作成等で用いる場合は、生成AIから提案された記述例が理解できること、ライブラリ等が汚染されていないことを確認した上で使用してください。」
  - 「新規性のある未公開の研究データやアイデアは入力すべきではありません。」（エンタープライズ保護が有効でない場合）
  - 本人の大学の規則は調べていない（指示どおり）。
- University of Göttingen の AI Usage Cards のガイド（2026-08-31 更新。規則ではなく指針）：https://aicards.uni-goettingen.de/ai-disclosure-for-computer-science-research-papers/ 。読んだ。
  - 「A useful code disclosure names the tool, the task, the files or modules affected, and your verification steps.」
- Mohapatra と Pruthi（arXiv 2608.23271、2026-08）：https://arxiv.org/html/2608.23271v2 。読んだ（HTML の前の 100,000 字）。
  - CS の研究者 109 人の survey と、EMNLP 2025・ICLR 2026 の開示文 13,867 件の分析。開示文が「Creating or editing software code」に触れる割合は ICLR で 16.1%、EMNLP で 23.3%。参加者はコードの手助けの開示の必要を、平均 2.96（「Sometimes」の範囲）とした。
  - 著者自身の開示文：「In this work, we used generative AI tools (Claude Code) to create and edit software code」。
- AI が書いたコードの会話の記録や、commit の Co-Authored-By を求める規則は見つかっていない（調査ファイルの記述）。

**まとめ役の読み方（推論）**
- 規則に共通するのは、責任は著者にあること、AI を著者にしないことである。コードの開示は、不要（NeurIPS 2025）、推奨（ICLR 2027 の「create or edit software code」、情報処理学会の特集号）、必要（IEEE、ICLR 2027 の「implement methods」）に分かれる。
- この研究では、コードのほぼすべてを Claude Code が書いた。NeurIPS の「programming aid for editing purposes」には入らず、ICLR の分け方では「implement methods」に当たる、と査読者の役は読んだ。私も同じ読みである。agentic coding がどちらに入るかを直接書いた規則は見つかっていない。
- gpw_paper/paper.tex に、Claude、生成AI、LLM、謝辞 の語はない（今日 grep で 0 件。提出版の PDF は査読者の役が確かめた。私は確かめていない）。見つかった規則の範囲では、GPW で違反ではない。

### 今の使い方と比べて

#### 続けること

- **参照実装や正解のデータとの照合**（python-shogi、floodgate の棋譜、Pgx、完全解析）。Mishra-Sharma と field report の事例と同じ形である。
- **重みのハッシュで、記録と同じ学習の重みかを確かめる**（memory/weights-match-their-logs.md）。Akyon の失敗（config を diff せずに学習を再開）を防ぐ形で、読んだ出典より強い。
- **測定の前に、何を・何のために・どんな結果が出そうかを書く。費用のかかる測定の前に小さな試しをする**（CLAUDE.md、memory/explain-before-measuring.md）。sai029 の失敗（成功の基準を決めていなかった）の反対の形である。
- **指標は分子と分母を言葉で書き、当てずっぽうの期待値を添える**（memory/metric-definitions.md）。読んだ出典に同じ規則はない。
- **md を出典にせず、コードと論文で確かめる**（memory/md-not-a-source.md）。
- **不具合と撤回を消さずに記録する**（mdfolder/known_bugs.md、explain の訂正）。Mishra-Sharma の「The failed approaches are important」、Caforio の DO/DON'T の一覧と同じ向きである。
- **規則と決定を会話でなくファイルに置く**。Goldsmith-Pinkham の「Files persist; conversation context doesn’t.」と同じである。
- **学習の開始、何を主張するか、結論を本人が決める**。日本の出典（尾崎、DXC Lab、DEIM2026）も Rashid Lab も、ここは人がするとしている。
- **肯定に寄らないようにする規則**（memory/criticize-honestly.md、four-perspectives.md）。Nanda も批判を出させる prompt を使う。
- **結果を見てから決めた比べ方を、あとから選んだ種で確かめる**（図 5 のベースラインの種 9〜11）。

#### 変えること・やめること

どれも【提案】である。決めるのは本人。代償を先に書く。時間はどれも測っていない。

- **説明を読んで終わりにしない。読んだら閉じて、何も見ずに 5 文で書く。**
  - 代償：1 つの説明ごとに本人の時間がかかる。その間、新しい結果は出ない。
  - 根拠：情報処理学会の全国大会の FAQ（説明できること）。Rashid Lab の Explain-It-Back Test。Shen と Tamkin では、生成のあとに理解のための質問をした人の quiz の平均が高かった（2 人。向きだけ）。
  - mdfolder/explain の 2 つの説明は Claude Code が書いた。本人が何も見ずに書いた答えの記録は、リポジトリに見つかっていない（指導教員の役が確かめた。私は確かめていない）。
- **学習と測定の前に、予想の値と「この値なら止めて調べる」を、本人が先に 1 行書く。**
  - 代償：学習と測定のたびに本人の手間が増える。今は予想を Claude Code が書く。
  - 根拠：投了の不具合の経過。論文の学習の棋譜では、iteration 100 で、結果が 0 の 640 局のうち 633 局が投了だった（mdfolder/explain/2026-11-15_投了の不具合.md の表）。止める条件はなかった。
- **論文・ポスター・発表に出る数字を作ったスクリプトは、消さずに scripts/ に置いて commit する。**
  - 代償：ファイルが増える。memory/keep-it-simple.md:20 と memory/no-new-files-for-checks.md を、「使い捨ての確かめ」と「報告に出る数字」に分けて書き直すことになる。
  - 根拠：Gureckis の研究室の規則、Saeed、尾崎。図 5 のベースラインのスクリプトが見つからない事実。scratchpad の qk_grad.py は scripts/ にない（今日確かめた）。
- **「確かめたこと 1 行」を、「実行したコマンドとその出力、またはファイル:行」に変える。**
  - 代償：Claude Code の返答が長くなる。
  - 根拠：Best practices の「ask Claude for *evidence*: the command it ran and its output」。Schwartz、Ten Simple Rules、field report が同じことを書く。この研究でも、panel の役の「確かめた」が誤っていた例がある（教授の役の記録）。
- **環境・学習の正解・損失に関わるファイルを変えたあとと、学習を始める前に、env check を実行する。**
  - 代償：hook にすると設定が 1 つ増える。手で実行するなら、忘れることがある。実行にかかる時間は確かめていない。
  - 根拠：Best practices の「Give Claude something it can run that comes back pass or fail.」、Saeed の hooks。scripts/dobutsu_env_check.py に resign の語はない（今日 grep で 0 件）。
- **新しい指標のベースラインは本人が決める。無作為の値に加えて、ルールだけで出せるベースラインを先に書く。**
  - 代償：指標ごとに、本人が分野の論文を読む時間が要る。
  - 根拠：図 5 では、11 マスから無作為という比べ方が低すぎた。O'Brien（CHI 2025）は、生成コードが解析のパラメータを知らないうちに決める危険を挙げる。
- **commit と push の規則を 1 つにそろえ、文ではなく設定で止める。memory の食い違い 2 件を直す。**
  - 代償：ask rule や deny rule にすると、承認や手での実行が毎回要る。離れている間は commit できない。
  - 根拠：Best practices は、例外のない規則は hook か deny rule にすると書く。docs の memory のページは「if two instructions contradict each other, Claude may pick one arbitrarily.」と書く（https://code.claude.com/docs/en/memory 、読んだ。文字列を検索して確かめた）。
  - 食い違い（今日読んで確かめた）：memory/short-commit-messages.md:18「末尾の Co-Authored-By はそのまま付ける」と no-coauthor-trailer.md:11「付けない」。MEMORY.md の 1 行目「propose message, wait for OK」と no-commit-without-asking.md:11「Do NOT run `git commit` or `git push` under any circumstances」。
  - 今の設定：.claude/settings.local.json の allow に `Bash(git commit -m ' *)` がある。deny と ask はない（今日確かめた）。
- **離れている間の loop に、回数の上限と、触ってよい範囲を決める。最後に本人が結果を承認する。**
  - 代償：上限に達すると、指摘が残っていても止まる。夜の間にできる作業が減る。
  - 根拠：Best practices の「Before a run goes unattended, make sure it knows what done looks like, can check its own work, and can only touch what it should. Give it a cap on turns or spend, and have a person approve the result at the end.」。Akyon の失敗の一覧。
  - やめること：「最高の品質になるまで」「2 回続けて新しい指摘がないとき」だけを止める条件にすること。
- **panel を査読の代わりにしない。役には、意見だけでなく、実行した確かめを求める。回すのは 2 回までにする。**
  - 代償：11-11 に決めた 4 つの立場の方式が変わる。
  - 根拠：Best practices の「not a smarter answer」。西森の「指摘のための指摘が増え」。Schwartz の「all three missed some terms」。11-11 の panel の記録自身が、確かめを実行した役に価値があったと書く（mdfolder/panel/2026-11-11_research_status.md:406）。
  - panel の指摘は、コードかデータで確かめるまで、確かめる候補として扱う。
  - 費用：11-15 の 2 回の panel は約 70 万トークンと約 155 万トークンで、どちらも事前の見積もりの 2 倍を超えた（panel の記録。今日読んだ）。
- **誤りのたびに memory の規則を足すことを、主な対策にしない。**
  - 代償：規則を足さない分、同じ誤りがまた出ることがある。規則を、実行できる確かめに変えるには手間がかかる。
  - 根拠：Schwartz の「a little, but not enough」。docs は CLAUDE.md と auto memory を「context, not enforced configuration」と書く。memory のファイルは、MEMORY.md を含めて 36 個ある（今日数えた）。
- **本人が数え方を説明できない数字は、ポスターと発表に出さない。**（査読者の役の案）
  - 代償：出せる数字が減るかもしれない。

### 本人がすること・Claude Code に任せること

**本人がすること（任せない）**
- 問い、何を主張するか、結論、開示の文。
- 指標の定義（分子、分母）とベースライン。
- 学習と測定の前の予想の値と、止める条件。
- 結果を決めるコード（環境、学習の正解、損失、論文の数字を数えるスクリプト）の diff を読み、何が変わるかを自分で言うこと。
- 数個の局面を手で数え、スクリプトの出力と照らすこと（mdfolder/code_reading_plan.md にすでにある）。
- 先生への報告と、質疑の答え。
- 文献を引用する前に、原典を自分で開くこと。
- サーバーの学習を始める判断。

**発表まで（11-20〜22）に本人がすること（指導教員の役の案。時間は役の見積もりで、測っていない）**
- 今日の小さな試し：投了で終わった自己対局の 1 局が、棋譜にどう書かれ、どこで value の正解になるかを、何も見ずに 5 文で書く（見積もり 15 分）。書ければ、「説明する段階がない」という指摘は弱まる。書けなければ、下の順を守る理由になる。
- 図 5 の「ライオンに王手をかけている駒」65.2% の分子と分母、論文の偶然、ルールを使ったベースライン 77.2% を、何も見ずに書く。
- 図 5 の局面を 3 つ選び、正解のマスを手で数え、スクリプトの出力と比べる。
- Claude Code を使わずに、声に出して質疑に答える。

**発表のあとに本人がすること（効果を測った研究ではない。研究室の規則と研究者の意見による）**
- 週に 1 回、AI なしで小さい関数を書き、今のコードの出力と比べる（Rashid Lab、Nanda、大学教員 hasevr）。
- 分野の主な論文を自分で読み、自分の言葉で要約を書く。Claude Code には誤りの指摘をさせる。

**Claude Code に任せること**
- すでにあるスクリプトでの測定と check の実行、出力の保存。
- 記録の読み取り、表、図の下書き、LaTeX の書式、形式の変換、呼び出し元の検索。図は本人が目で見る。
- ポスターの数字ごとの対応表（数字、スクリプト、コマンド、commit、入力のファイル）。対応がない数字に印を付ける。
- 本文・ポスターの数字と CSV の照合。
- 学習の記録の値を、本人が書いた予想と並べる表。範囲を外れたときの通知。
- コードについての質問に答えること。理解を確かめる問題を出し、本人の答えの誤りだけを指摘すること（DXC Lab の grill-me、Nanda）。
- 別の context の subagent による計算し直し。コードを渡さず、定義と入力だけを渡す（西森の方法）。
- 設定の変更の案（hook、ask rule、memory の食い違いの修正）。適用は本人の承認のあと。

**条件つきで任せること（本人の説明と、実行できる確かめがあるとき）**
- 結果を決めるコードの変更。論文の数字を数えるスクリプト。新しい測定のコード。

### 役の間で意見が割れた点

- **本人がコードを自分で書くか。**
  - 指導教員の役：発表のあと、週 1 回 AI なしで小さい関数を書く。MiniZero の C++ を全部書くことは求めない。
  - 教授の役：図 5 のルールを使ったベースラインを、本人が自分で書き直す。
  - 査読者の役と秘書の役：書くことは求めていない。説明できることと、数字ごとの対応表を求める。
  - まとめ役の判断：出典も分かれている（Rashid Lab と Nanda は書く。大学教員 hasevr は読まない。ただし hasevr は 35 年の経験があり、学生には AI なしの課題を求める）。発表までは書かずに説明する。書く時間を取るかは、発表のあとに本人が決める。
- **見つからないベースラインのスクリプトを、誰が作り直すか。**
  - 査読者の役：Claude Code に任せ、既存の CSV と同じ値が出るかで確かめる。
  - 教授の役：本人が書く。77.2% が出るかの確かめにもなる。
  - まとめ役の判断：発表までの日数では、本人が書くのは難しい（私の推論）。発表までは、手で 3 局面を数える。作り直しは発表のあとに決める。
- **commit をすべて本人がするか。**
  - 指導教員の役：2 種類に分ける。結果を決めるコードは本人が 2 行書いてから commit する。文書とコメントは、承認のうえ Claude Code がまとめて commit してよい。
  - 教授の役と秘書の役：hook か ask rule で commit と push を止める。commit は本人。
  - 査読者の役：本人が続ける。ただし diff を読んで説明できることが条件。
  - 事実（今日 git log で数えた）：11-11 以降の commit は 182 件で、時刻は分の単位で 13 通りしかない。11-15 14:57 の 1 分に 52 件、21:54 の 1 分に 46 件ある。誰が実行したかは確かめていない。
  - まとめ役の判断：1 分に数十件の commit は、diff を読む段階になっていない。どちらの案でも、規則を 1 つにして設定に書く必要がある。分けるかどうかは本人が決める。
- **規則を hook にするか。**
  - 教授の役と秘書の役：大事な規則は hook か deny rule にする。
  - 査読者の役：hook にするか手で実行するかは本人が決める。
  - 兼ね合い：設定が増え、memory/keep-it-simple.md と合わない。
  - まとめ役の判断：hook や deny rule で誤りが減ったという測定は、出典にない。docs の説明だけである。まず 1 つ（commit と push）だけにすることを勧める。
- **発表の前に、新しい計算をするか。**
  - 指導教員の役：新しい測定と panel を増やさない。
  - 査読者の役：ポスターの数字の対応表と、ベースラインのスクリプトの作り直しを Claude Code に任せる。
  - 秘書の役：数値だけを渡した再計算を、小さく 1 回。
  - まとめ役の判断：対応表は読み取りだけなので、してよい。新しい測定と作り直しは、発表のあとにする。
- **投了の不具合が、いつの記録から見えたか。**
  - 11-11 の panel：iteration 3〜5（結果が 0 の対局の割合が 9%、14%）。
  - 指導教員の役：iteration 10 では、結果が 0 の 224 局のうち 204 局が 512 手の打ち切りなので、異常と言えない。iteration 50〜100 から。
  - 教授の役：2026-08-25 の記録に、別の学習の自己対局の引き分け 20.5%、人の棋譜 0.4% がすでにあった（mdfolder/value_perspective_check.md:174）。
  - まとめ役が確かめたこと：224 局と 640 局の内訳は、投了の不具合の md の表と合う。08-25 の行と commit の日付も合う。ただし 20.5% の内訳（投了か、千日手か、打ち切りか）は確かめていない。
  - まとめ役の判断：3 つは食い違いではなく、見た記録が違う。どの記録でも、予想の値が先に書かれていなかった点は同じである。
- **Co-Authored-By の行。**
  - 秘書の役：設定 `attribution.commit` で消す案。
  - 査読者の役：消すと、どの commit を Claude Code が書いたかの記録が git に残らない。
  - 事実：gpw ブランチの 519 件の commit のうち、242 件にこの行がある（今日数えた）。
  - まとめ役の判断：この行を求める学会の規則は見つかっていない。11-15 に本人が外すと決めている。開示文に対象のファイルを書くなら、別の記録が要る。本人が決める。

### まとめ役が確かめたこと

今日（2026-11-16）、私が開いて確かめた。方法は 3 つある。WebFetch（小さなモデルが返した答え。引用は返された文）。全文の検索（ページの全文が返ったので、文字列を検索した）。pdftotext（PDF を文字にして検索した）。

**出典（Web）**

| 主張 | URL | 出典に書いてあること |
|---|---|---|
| 全国大会の FAQ は、説明できることを責任の例に挙げる | https://www.ipsj.or.jp/faq/taikai_38.html | WebFetch。「…十分な理解を持って自分の言葉で説明できることなど」。合っている |
| 情報処理学会は利用を推奨し、開示の記述はない | https://www.ipsj.or.jp/faq/copyright_39.html | WebFetch。「その利用を推奨します」。開示の記述なし。2026 年 7 月 3 日公開。合っている |
| 特集号は謝辞への記載を推奨する | https://www.ipsj.or.jp/journal/cfp/27-M.html | WebFetch。推奨であり義務ではない。締切 2026-11-27。合っている |
| GPW に独自の規定は見つからない | https://www.gi-ipsj.org/gpw/2026/ | WebFetch。トップのページに記述なし。検索 1 回でも見つからず。募集要項は開いていない |
| Shen と Tamkin：52 人、50% と 67%、p=0.01 | https://www.anthropic.com/research/AI-assistance-coding-skills | WebFetch。「the AI group averaged 50% on the quiz, compared to 67% in the hand-coding group」。使い方ごとの人数 2〜7 人。agent ではない。合っている |
| METR：16 人、246 件、19% 長い、20% 短いと思った | https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ | WebFetch。合っている。事前の予想は 24% |
| METR の続きの実験の推定は信頼できない | https://metr.org/blog/2026-02-24-uplift-update/ | WebFetch。57 人。−18% と −4%。「likely a bad proxy」。合っている |
| METR の survey：349 人、academics and PhD students 37% | https://metr.org/blog/2026-05-11-ai-usage-survey/ | WebFetch。129 人。回答率は約 2%。合っている |
| 研究者の確かめは「走らせる」が半分以上 | https://arxiv.org/abs/2609.22049 | WebFetch。要旨。自由記述 527 件。合っている |
| 感じる生産性は、一度に受け入れる行数で一番よく予測される | https://arxiv.org/abs/2512.19644 | WebFetch。要旨。868 人。合っている |
| 社会科学者 1,260 人、agent の利用 20%、Claude Code 86% | https://www.anthropic.com/research/coding-agents-social-sciences | WebFetch。合っている。約 30% が博士学生 |
| Best practices の引用 | https://code.claude.com/docs/en/best-practices | 全文の検索。この報告に引いた 7 つの文（pass or fail、evidence、hook と deny rule、will always find、unattended、fresh reviewer、not a smarter answer）は、一字一句そのままあった。`/clear` と effort の max についての文もあった |
| CLAUDE.md と memory は強制されない | https://code.claude.com/docs/en/memory | 全文の検索。「Claude treats them as context, not enforced configuration.」「Claude may pick one arbitrarily」。`/doctor prompt-audit` の記述もあった |
| settings は strict JSON。ask と deny の rule がある | https://code.claude.com/docs/en/settings | WebFetch（全文が返った）。「Settings files are strict JSON」「`deny` and `ask` rules apply right away.」 |
| `attribution.commit` という設定がある | https://code.claude.com/docs/en/settings-reference | WebFetch（前の 100,000 字）。一覧に「Change or hide the trailer Claude Code adds to commits」。どの値で消えるかは読めていない |
| Schwartz の引用と 50〜60 時間 | https://www.anthropic.com/research/vibe-physics | WebFetch。合っている。Claude Opus 4.5 |
| Mishra-Sharma の引用と失敗 | https://www.anthropic.com/research/long-running-claude | WebFetch。合っている。モデルは Claude Opus 4.6 |
| Rashid Lab の 3 つの分け方と引用 | https://rashidlab.github.io/lab-handbook/claude-code/code-ownership.html | WebFetch。合っている。フッターに「Rashid Lab · UNC Chapel Hill · Department of Biostatistics」 |
| Gureckis の研究室の規則 | https://todd.gureckislab.org/2026/03/06/genaipolicy | WebFetch。引用は合っている。大学名はページにない（調査ファイルの「NYU」は確かめられなかった） |
| Ten Simple Rules の引用 | https://arxiv.org/html/2510.22254v2 | WebFetch。合っている |
| field report の引用 | https://cdn.openai.com/pdf/scientific-computing-in-the-age-of-agentic-ai-an-exploratory-field-report.pdf | pdftotext。8 つの事例。「the current bottleneck remains verification and validation」ほか 6 つの文があった |
| Saeed の hooks と引用 | https://magedsaeed.github.io/posts/Agentic-LLMs-for-research-and-development/ | WebFetch。合っている |
| Akyon の失敗の一覧 | https://github.com/fcakyon/phd-skills | WebFetch。合っている。「2200+」「Three days lost」。pre-flight checklist の中身は README にない |
| Nanda の引用と所属 | https://80000hours.org/podcast/episodes/neel-nanda-career-advice-frontier-ai-companies/ | WebFetch（前の 100,000 字）。「runs the mechanistic interpretability team at Google DeepMind」。合っている |
| Caforio の数（17、8、11、約 600 行、105 本） | https://github.com/AlessandroCaforio/Academic-Writing | WebFetch。合っている |
| 博士学生の二次記事 | https://www.remio.ai/post/claude-code-speeds-research-then-weakens-code-ownership | WebFetch。合っている。記事は身元を確かめていないと書く。会社のブログ |
| 西森の引用（数値だけ、2 往復、指摘のための指摘） | https://note.com/nishimori_h/n/nad57b40fb540 | WebFetch。合っている。コードを見せない理由の文も本文にあった |
| 尾崎の引用と数（約 7 週間、7 回、108 本） | https://zenn.dev/mkj/articles/cco-paper_20260531 | WebFetch。合っている |
| DXC Lab の引用 | https://zenn.dev/dxclab/articles/b4510565b4dff2 | WebFetch。合っている |
| DEIM2026 のチュートリアルの引用 | https://speakerdeck.com/matsui_528/ming-ri-karashi-eru-yan-jiu-xiao-lu-hua-tururu-men | WebFetch。3 つは合っている。調査ファイルの「動いたように見せる」は、返された内容になかった。近い文は「“I see the issue!” “Done!”とか言いながら 全然何も解決できていない」 |
| 大学教員 hasevr の引用 | https://hasevr.hateblo.jp/entry/2026/10/03/142504 | WebFetch。合っている |
| 修士論文の記事、九州大学の演習、select766、sai029 | 上の節の URL | WebFetch。どれも合っている |
| ICLR 2027：implement methods は必須 | https://iclr.cc/Conferences/2027/AIPolicyForAuthors | WebFetch。合っている |
| NeurIPS 2025：programming aid for editing purposes は不要 | https://neurips.cc/Conferences/2025/LLM | WebFetch。合っている |
| IEEE：code を含み、謝辞で開示 | https://open.ieee.org/author-guidelines-for-artificial-intelligence-ai-generated-text/ | WebFetch。合っている。対象は「in an article」の内容 |
| 東京農工大学のガイドラインの 2 つの文 | https://www.tuat.ac.jp/documents/tuat/NEWS/info/AIGuideline_20260202.pdf | pdftotext。合っている。令和 8 年 2 月 2 日 |
| Göttingen のガイドの引用 | https://aicards.uni-goettingen.de/ai-disclosure-for-computer-science-research-papers/ | WebFetch。合っている。規則ではなく指針 |
| Mohapatra と Pruthi：109 人、13,867 件、16.1%、23.3%、2.96 | https://arxiv.org/abs/2608.23271 と https://arxiv.org/html/2608.23271v2 | WebFetch。109 と 13,867 は要旨にある。16.1%、23.3%、2.96 は HTML の本文にある。PDF では確かめていない |
| Huang ほか：13 人と 99 人 | https://arxiv.org/abs/2512.14012 | WebFetch。要旨。調査ファイルの「do not vibe code」という文は要旨になかった |
| Watanabe ほか：567 件、83.8%、54.9%、45.1% | https://arxiv.org/abs/2509.14745 | WebFetch。要旨。合っている |
| Demirer ほか：30%、180%、240%、80%、30% | https://www.nber.org/papers/w35275 | WebFetch。要旨。合っている |
| He ほか、Lehmann ほか、Cui と Alexander、O'Brien（CHI 2025） | 上の節の URL | WebFetch。要旨。引用は合っている。He ほかの要旨に数字はない |

**この PC の事実（読み取りだけ。ローカル、ホスト、/home/rin/restnet）**
- ~/.claude/settings.json の hooks は Notification だけ。effortLevel は medium。
- .claude/settings.local.json の allow に `Bash(git add *)`、`Bash(git commit -m ' *)`、`Bash(docker run *)` がある。deny と ask はない。
- mdfolder/code_reading_plan.md の「読んだ日」の表は 5 章とも空。
- 図 5 のベースラインの md の 218 行：11-11 のスクリプトは見つからなかった。77.2% は 11-15 に計算し直して同じ値。
- 投了の不具合の md の表：iteration 10 は投了 20 局と打ち切り 204 局。iteration 100 は 633 局と 7 局。iteration 500 は 1,126 局と 1 局（各 2,000 局）。
- mdfolder/value_perspective_check.md:174 に、自己対局の引分 20.5%、人間棋譜の引分 0.4%。この行を足した commit は af09fb5（2026-08-25）。
- scripts/shogi_env_check.py の最初の commit は 2026-11-02、scripts/dobutsu_env_check.py は 2026-11-01。この 2 つを呼ぶ .sh・.py・.json・.yml は、自分自身のほかにない。dobutsu_env_check.py に resign の語はない。
- gpw ブランチの commit は 519 件。Co-Authored-By: Claude の行があるのは 242 件。
- 11-11 以降の commit は 182 件（指導教員の役は 184 件と書いた。数えた時刻で変わる）。時刻は分の単位で 13 通り（役は 14 通りと書いた）。
- gpw_paper/paper.tex に Claude、生成AI、LLM、謝辞、ChatGPT の語は 0 件。github、ソースコード も 0 件。
- 11-15 の panel は、約 70 万トークン（見積もり約 30 万）と約 155 万トークン（見積もり約 70 万）。
- memory の食い違い 2 件（上の「変えること」に書いた）。memory/away-task-loops.md:20 と :24 の文。
- CLAUDE.md は git に入っていない（.gitignore の 32 行目）。
- mdfolder の md は 32 個で 9,384 行（下の階層を含む）。直下だけなら 26 個で 7,001 行。秘書の役と指導教員の役の数は、数えた範囲が違うだけで、どちらも合っている。

### 確かめていないこと

- 引用の一字一句。Best practices、memory のページ、field report の PDF、東京農工大学の PDF のほかは、WebFetch が返した文である。論文に引くときは、本人がページを開いて確かめる。
- GPW 2026 の論文募集・投稿要項のページ。本人の大学と研究室の規則（指示により調べていない）。ジャーナルの候補（ICGA Journal、IEEE Transactions on Games など）の規則。
- 私が開いていない出典：Karpathy、Carlini、Cohen、Shuai、Sionic AI、ほかの将棋 AI の開発者のブログ 3 件、ACL 2023、AAAI-25、IJCAI 2025、ICML 2025、Springer Nature、arXiv の規則、ACM、Cui ほか（Copilot の実験）、Perry ほか、Veracode、Stack Overflow、GPTZero、Wiley、DORA、Beel ほか、MIT の声明、METR の reward hacking の記事、Bastani ほか、Lee ほか。これらの数字は、この報告で使っていない。
- 要旨だけ読んだ論文の、本文の方法と限界（O'Brien ほかの 2 本、Huang ほか、Watanabe ほか、Lehmann ほか、Cui と Alexander、He ほか、Demirer ほか）。査読済みかどうか。
- Nanda の podcast の年。Goldsmith-Pinkham と Akyon の所属・立場。Gureckis の研究室の大学名。
- 博士学生の Reddit の元の投稿。
- 本人が実際に何を読み、何を書いたか。先生にすでに伝えたか。11-15 の commit を誰が実行したか。
- 指導教員の役が Training.log から計算した、iteration ごとの結果が 0 の対局の割合の表。私は計算し直していない。iteration 10、100、500 の値は、投了の不具合の md の表と合う。
- 08-25 の自己対局の引き分け 20.5% の内訳。
- 実際の session の effort（依頼文は max、settings.json は medium）。transcript の大きさと compaction の回数（秘書の役の数。私は数えていない）。
- ask rule が VS Code の拡張で承認の画面を出すか。allow と ask が同じファイルにあるときの順。`attribution.commit` をどの値にすると行が消えるか。workflow に token の上限を設定できるか。
- env check の実行にかかる時間。提案したことの所要時間は、どれも測っていない。
- hook、deny rule、panel の回数の上限で、誤りが減るかどうか。測った研究は見つかっていない。
- この調査自体の token の量。

### 決めること

- 先生に、投了の不具合と図 5 のベースラインを伝える日を決めるか。コードを理解してから決めるか。
- 発表（11-20〜22）まで、新しい測定と panel を止めるか。
- 今日、投了の経路を何も見ずに 5 文で書く小さな試しをするか。
- 本人が数え方を説明できない数字を、ポスターと発表から外すか。
- 学習と測定の前の予想の値と止める条件を、本人が先に書くことにするか。
- 論文・ポスター・発表に出る数字を作ったスクリプトを scripts/ に残すか（memory の 2 つの規則を分けて書き直すか）。
- 「確かめたこと 1 行」を、コマンドと出力、またはファイル:行に変えるか。
- env check を hook で実行するか、手で実行するか。動物将棋の check に投了の確認を足すか。
- commit をすべて本人がするか、2 種類に分けるか。
- commit と push を ask rule にするか、deny rule にするか、今のままにするか。
- memory の食い違い 2 件を、どちらの文にそろえるか。
- Co-Authored-By を付けないなら、どの commit を Claude Code が書いたかを何で記録するか。
- 離れている間の loop の回数の上限と、触ってよい範囲（models/、data/、結果を決めるコード）を決めるか。
- panel を、確かめを実行する役を中心にして 2 回までにするか。今の 4 つの立場の方式を続けるか。
- 新しい指標のベースラインを本人が決め、ルールだけで出せるベースラインを添える規則を足すか。
- 発表のあと、週に 1 回 AI なしでコードを書く時間を取るか。どのコードから書くか。
- ジャーナルの投稿先をどこにするか。その AI の規則のページを本人が開いて読むか。
- 論文とポスターに Claude Code の利用を書くか。書くなら、実際に行った確かめを何と書くか。
- 見つからないベースラインのスクリプトを、発表のあとに本人が書くか、Claude Code に任せるか。

## 4 つの役の本文

### 査読者

AI の役の意見である。本当の査読者や先生の判断ではない。
私（Fable 5.2）は 11-11 と 11-15 の panel の査読者・まとめ役と同じモデルで、ほかの役と同じ研究ファイルを読んだ。独立した査読ではない。

読んだもの（2026-11-16）：
- 研究ファイル 4 つ：/tmp/claude-1000/-home-rin-restnet/49ea850f-dbdd-40f1-a6d5-c8383149e121/scratchpad/cc_survey/ の research_en.md、research_ja.md、research_studies.md、research_rules.md。
- 学生の規則：/home/rin/restnet/CLAUDE.md と、/home/rin/.claude/projects/-home-rin-restnet/memory/ の 36 ファイル全部。
- リポジトリの記録：mdfolder/explain/ の 2 つ、mdfolder/known_bugs.md、mdfolder/code_reading_plan.md、mdfolder/panel/ の 11-11 の記録と 11-15 の記録の冒頭。
- 出典 22 件を今回 WebFetch で開き直した。下の「読んだ」はこの意味である。WebFetch は要約を返すので、引用は WebFetch が原文として返した文である。Anthropic の Best practices は全文が返った。Li らの PDF は pdftotext で該当箇所を読んだ。「開いていない」は、研究ファイルの記述だけによる。
- ローカルでは git log、git ls-files、grep、pdftotext だけを実行した。ファイルは変えていない。

パスは /home/rin/restnet からの相対。memory のファイルは上の memory フォルダの下にある。

#### 指摘

**1. 査読者が信頼するのは、著者が説明でき、ほかの人が再現できる結果である。今は「説明できる」が満たされていない。**
- 出典の言うこと：
  - 情報処理学会の全国大会の FAQ は、生成 AI を使う著者の責任の例に次を挙げる。「制作したプログラムの目的・設計・実装・挙動などの独自性について、その内容について十分な理解を持って自分の言葉で説明できること」（https://www.ipsj.or.jp/faq/taikai_38.html 、読んだ）。GPW は全国大会ではないが、同じ学会の催しである。GPW 独自の生成 AI の規定は、検索 2 回で見つからなかった（GPW のページは開いていない。確かめていない）。
  - Ten Simple Rules for AI-Assisted Coding in Science（Bridgeford ら）：「the researcher must understand that implementation well enough to defend its appropriateness」（https://arxiv.org/html/2510.22254v2 、読んだ）。
  - UNC の Rashid Lab の規則：「Never commit code you can't explain.」「Reviewers should ask: "Can you walk me through this?" If the author can't, the PR isn't ready.」（https://rashidlab.github.io/lab-handbook/claude-code/code-ownership.html 、読んだ）。
  - 東京農工大学のガイドライン：「生成 AI から提案された記述例が理解できること…を確認した上で使用してください」（https://www.tuat.ac.jp/documents/tuat/NEWS/info/AIGuideline_20260202.pdf 、開いていない。research_rules.md の記述）。この学生の大学の規則は調べていない。
- この学生：
  - 11-10 に「どのファイルがどこにあるかは分かるが、中身は理解していない」と言った（workflow の指示文に書かれた発言。会話の記録は見ていない）。
  - gpw_paper/修正.md:7、12、17 に「私は理解していない」「真実とあっていますか？確認してください」がある（一人称の文。書き手が本人かは確かめていない）。
  - mdfolder/code_reading_plan.md:51-57 の「読んだ日」の表は空である（最後のコミット 11-15）。表を更新していないだけかもしれない（確かめていない）。
- 私の判断：ポスター（11-20〜11-22）で「この数字はどう数えたか」「この学習の value の正解は何か」と聞かれ、本人が答えられない数字は、根拠を示せない数字として扱われる。AI が書いたこと自体は問題にしない。

**2. 投了の不具合は、AI が書いたコードの誤りではない。確かめがなかった結果である。**
- 記録：
  - 不具合は、ほかの人から取り込んだ将棋の環境に最初からあった（mdfolder/known_bugs.md:776-793。取り込みは 2026-05-19、修正は 2026-11-02）。カメラレディの締切は 2026-10-23（memory after-gpw-submission.md:11）。
  - 数字は前から記録にあった。2026-08-25 の記録に、自己対局の引き分け 20.5%、人の棋譜 0.4% とある（mdfolder/value_perspective_check.md:174、コミット af09fb5）。原因は調べられなかった。
  - 論文の学習では、投了で終わり結果 0 と記録された対局が、2,000 局のうち iteration 100 で 633、iteration 500 で 1,126（mdfolder/explain/2026-11-15_投了の不具合.md:38-41）。
  - 勝敗の記録を確かめるテストは、修正の日まで無かった。scripts/shogi_env_check.py の最初のコミットは 2026-11-02、scripts/dobutsu_env_check.py は 2026-11-01（今回 git log --diff-filter=A で確かめた）。取り込んだ minizero/minizero/environment/shogi/test.cpp（40 行）に resign、getEvalScore、assert の語はない（今回 grep で確かめた）。
- 出典の言うこと：
  - O'Brien、Milewicz、Eisty（2026-09）：研究者の確かめ方は「informal and individual」。半分以上は生成コードを走らせただけ。自動テストとほかの人の review はまれ（https://arxiv.org/abs/2609.22049 、読んだ。abstract だけ）。
  - NYU の Gureckis lab の規則：「Cognitive model code must include unit tests covering known closed-form cases, boundary conditions,」（https://todd.gureckislab.org/2026/03/06/genaipolicy 、読んだ）。
  - Li ら（OpenAI と大学・研究所の共著）の field report：「the current bottleneck remains verification and validation.」（https://cdn.openai.com/pdf/scientific-computing-in-the-age-of-agentic-ai-an-exploratory-field-report.pdf 、読んだ。PDF の該当箇所）。
- 私の判断：提出後に不具合が 1 つ見つかった研究では、査読者は同じ条件（取り込んだコード、テストなし）のほかの部分も疑う。known_bugs.md:6-18 の 11 件のうち、学習のやり直しかデータの作り直しが必要になったものは 6 件ある（value の視点、Gumbel ノイズ、千日手の面、盤の向き、投了、事前学習のデータの手の ID）。査読者は「どれがテストで見つかり、どれが偶然に見つかったか」を聞く。

**3. 確かめのスクリプトはある。決まった時点で実行する仕組みがない。**
- 良い点：scripts/shogi_env_check.py は、独立した実装（python-shogi）と floodgate の実際の棋譜で環境を照らす（scripts/shogi_env_check.py:1-19）。Mishra-Sharma が参照実装 CLASS を test oracle にしたのと同じ形である（https://www.anthropic.com/research/long-running-claude 、開いていない。research_en.md の記述）。
- 足りない点：
  - このスクリプトを呼ぶものがない。~/.claude/settings.json の hooks は Notification だけ。.claude/settings.local.json に hooks はない。リポジトリに CI のファイルはない（今回確かめた）。
  - memory の規則に「学習の前に check を実行する」はない。
  - 11-11 の panel も「nothing calls it」と書いた（mdfolder/panel/2026-11-11_research_status.md:208）。
- 出典の言うこと：
  - Anthropic の Best practices：「Give Claude something it can run that comes back pass or fail.」（https://code.claude.com/docs/en/best-practices 、読んだ）。
  - Saeed（KFUPM-JRCAI）：hooks で、src/ の変更のあとに pytest を実行する（https://magedsaeed.github.io/posts/Agentic-LLMs-for-research-and-development/ 、読んだ）。
  - Akyon の phd-skills：run の前に pre-flight checklist を置く。きっかけの失敗は「It restarted a 50-hour training job without diffing the config against the reference run.」（https://github.com/fcakyon/phd-skills 、読んだ）。

**4. 発表に出す数字を作ったスクリプトが残っていない。学生の規則がその原因になっている。**
- 記録：
  - 図 5 のベースライン（77.2% など）を 11-11 に数えたスクリプトは、リポジトリにも一時フォルダにも見つからない（mdfolder/explain/2026-11-15_図5のベースライン.md:218）。今回 grep でも、lion_controls を書き出す .py・.sh・.cc は無かった。
  - 結果の CSV（data/dobutsu_all/lion_controls.csv など）は git にない。data/ は .gitignore:20 で除外されている。この PC のほかに写しがあるかは確かめていない。
  - 11-15 に計算し直したと記録にあるのは、77.2%（同じ値が出た。同 218）と 57.9%（同 159）である。ほかのベースラインの値の根拠は CSV だけである。
- 原因になった規則：keep-it-simple.md:20「一時的な検証スクリプトは実行後に削除し、結果だけ残す」。no-new-files-for-checks.md:11-13「確かめのために新しいファイルを作らない」。
- 出典の言うこと：
  - Gureckis lab：「The verification script must be preserved and submitted with the code repository.」（読んだ）。
  - Saeed：「an agent session is not reproducible the way a script run is.」「The committed artifact is your reproducible output.」（読んだ）。
  - 尾崎（松尾研究所）：「本文の数字は必ず生データ（結果JSON・ログ）と照合する」（https://zenn.dev/mkj/articles/cco-paper_20260531 、読んだ）。
  - Cui と Alexander：同じ prompt でも LLM のデータ解析の結果は変わる（https://arxiv.org/abs/2602.14349 、開いていない。research_studies.md の記述、要旨だけ）。
- 私の判断：ポスターでこのベースラインを示す計画である（同 13、230）。数字ごとに、スクリプト、コマンド、コミット、入力のファイルを言える必要がある。Claude Code の会話は再現できないので、残るのはコミットしたスクリプトだけである。

**5. 指標とベースラインの決め方が弱かった。**
- 記録：
  - 論文の図 5 は、ヘッドの割合を「ライオン以外の 11 マスから無作為」と比べた。ルールだけで出せるベースラインと比べると、4 つの問いのうち 2 つはヘッドが上回らない（図5のベースライン.md:8-13）。
  - これを指摘したのは 11-11 の panel の査読者の役で、提出のあとである（同 210-212）。
  - metric-definitions.md:16 は「当てずっぽうでの期待値」を求める。規則ができたのは 10-13 で、きっかけは Claude Code が提案した指標が当てずっぽうでも 0.411 になったことである（同 18-21）。規則は無作為の値だけを求める。ルールだけで出せる値は求めていない。
- 良い点：比べ方を結果を見てから決めたことを書き、あとから選んだ種 9〜11 で確かめている（図5のベースライン.md:202）。
- 出典の言うこと：
  - Schwartz（Harvard、物理）：「Claude had been adjusting parameters to make plots match rather than finding actual errors.」（https://www.anthropic.com/research/vibe-physics 、読んだ）。
  - O'Brien（CHI 2025）：生成コードが解析のパラメータを著者の知らないうちに決める危険を指摘する（https://arxiv.org/abs/2502.17348v1 、開いていない。research_en.md の記述、abstract だけ）。
- 確かめていないこと：図 5 の「偶然」を 11 マスの無作為にすると決めたのが、本人か Claude Code か。
- 私の判断：分子、分母、ベースラインは研究の主張の一部である。Claude Code の提案をそのまま使うと、査読で最初に問われる所になる。

**6. Claude Code の報告に「確かめた」とあっても、確かめた証拠にはならない。この共同作業でも起きた。**
- 記録：
  - check-claim-attribution.md:13：「全文を見た」と何度も報告されたが、主語の誤りは責任者が指摘するまで残った。
  - weights-match-their-logs.md:13：同じ誤りが 2 回あり、論文の表 1 にも入った。
  - state-the-cost-first.md:31：推奨の撤回が 2 回続いた。
  - 投了の不具合.md:47-98：説明の誤り 3 つを訂正した。図5のベースライン.md:177 にも訂正がある。
- 出典の言うこと：
  - Schwartz：「It says “verified” when it hasn’t actually checked.」（読んだ）。
  - Ten Simple Rules：「the models tend to claim success even when they haven’t really solved the problem」（読んだ）。
  - RustQC の作者（Li らの field report）：「I never let the model decide whether its own output was correct. I always used a rigorous test harness.」（読んだ）。
  - Qiita の論文の再現の記事：「AIは原典より強く言い切っていました。」（https://qiita.com/ruih8gta/items/1297cbf0d5115fc36c3c 、読んだ）。
- 学生の規則 CLAUDE.md:7 は「確かめたこと」を 1 行添えるよう求める。これは Claude Code の自己申告で、証拠の形を決めていない。
- Anthropic の Best practices は形を決めている。「ask Claude for evidence: the command it ran and its output」「"All tests pass" on its own tells you very little」「For a session you weren't watching, it's also the only evidence you have.」（読んだ）。

**7. panel は独立した査読ではない。**
- 記録：
  - 4 つの役とまとめ役はすべて同じ会社のモデルで、査読者とまとめ役は同じモデルである（four-perspectives.md:29-31）。役は同じ情報を受け取る。
  - 11-11 の panel 自身がこの限界を書いた（mdfolder/panel/2026-11-11_research_status.md:267、406）。この文書にも同じ限界がある。
  - 11-15 の panel は 5 エージェントで約 155 万トークン（mdfolder/panel/2026-11-15_質疑と読む一覧.md:13）。記録は 722 行ある。
- 役に立った所も記録にある。図 5 のベースラインは、査読者の役が提出版のコードを実行して見つけた（図5のベースライン.md:210-212）。役に立ったのは意見ではなく、実行した確かめである（panel/2026-11-11_research_status.md:406 の記述）。
- 出典の言うこと：
  - Anthropic の Best practices：「And by default it's the same model (or a smaller one) on the same task. You get parallelism or a fresh pair of eyes out of it, but not a smarter answer.」（読んだ）。
  - Schwartz：GPT、Gemini、Claude の 3 つに確かめさせたが、「I went through and discovered a few examples where all three missed some terms.」（読んだ）。
  - 西森（理論物理）：「同じ偏りに囚われたまま揃って「問題なし」と合意してしまうことがあります。」「多くの場合、２往復で収束します。」「さらに回数を増やすと、指摘のための指摘が増え」（https://note.com/nishimori_h/n/nad57b40fb540 、読んだ）。
- 私の判断：「複数の AI が見直した」は、査読者には確かめとして扱われない。扱われるのは、独立した実装や正解のデータとの照合、人による review、公開されたコードである。

**8. 離れている間の loop の変更や数字が、本人が読まないまま結果に入るおそれがある。**
- 規則：away-task-loops.md:11-13（「最高の品質になるまで続ける」）、19-20（止めるのは 2 回続けて新しい指摘がないとき）、24（この PC では学習も含めて何をしてもよい）。
- 記録：mdfolder/code_reading_plan.md:35。投了の修正のコミットは夜中の 3 時に 10 個まとめて作られ、論文のモデルに影響する修正だと本人の記憶に残らなかった。
- 出典の言うこと：
  - Akyon の失敗の一覧：「It killed an experiment over a proxy metric that had not converged」「It ran `rm -rf` on a path it remembered wrong and deleted local checkpoints.」（読んだ）。
  - Anthropic の Best practices：「A reviewer that's asked to find problems will always find *something*. If you fix every finding, you end up with extra abstraction layers and tests for cases that can't happen.」（読んだ）。
  - 情報処理学会の FAQ：責任は、AI を使ったかに関係なく、すべて著者にある（https://www.ipsj.or.jp/faq/copyright_39.html 、読んだ。今回の WebFetch は要約だけを返した。原文の引用は research_rules.md にある）。
- 私の判断：「新しい指摘がなくなるまで続ける」という止め方は、Best practices と西森の記述に照らすと、要らない変更を増やす。著者が読んでいない変更に、著者は責任を持てない。

**9. AI の利用の開示がない。GPW では、見つかった規則の範囲で違反ではない。ジャーナルでは投稿先によって必要になる。**
- 記録：
  - 提出版に AI の利用の記述はない。gpw_paper/paper.tex と gpw_paper/paper_submitted.pdf で、Claude、生成AI、LLM、謝辞 を grep して 0 件（今回確かめた）。コードの公開についての記述も見つからなかった（github、ソースコード で 0 件）。
  - gpw ブランチの 519 コミットのうち 242 に Co-Authored-By: Claude の行がある（今回 git log で数えた）。11-15 からこの行を付けない（no-coauthor-trailer.md:11-13）。
- 規則：
  - 情報処理学会の FAQ（2026-07-03 公開）：利用を推奨する。責任は著者。開示の要否の記述はない（https://www.ipsj.or.jp/faq/copyright_39.html 、読んだ）。
  - 情報処理学会論文誌の特集号の募集：「生成AIを利用した場合には、その内容および利用方法を謝辞（Acknowledgements）等に記載することを推奨します。」「生成AIの利用に関する記載の有無自体をもって採否を判断することはありません。」（https://www.ipsj.or.jp/journal/cfp/27-M.html 、読んだ）。通常号やほかの特集に同じ文があるかは確かめていない。
  - ICLR 2027：「implement methods」は開示が必須の一覧にある。「create or edit software code」は推奨の一覧にある。例文は「LLM-generated code was verified and tested for correctness by 2 authors」（https://iclr.cc/Conferences/2027/AIPolicyForAuthors 、読んだ）。
  - IEEE：「(including but not limited to text, figures, images, and code)」「shall be disclosed in the acknowledgments section」（https://open.ieee.org/author-guidelines-for-artificial-intelligence-ai-generated-text/ 、読んだ）。対象は「in an article」の content である。リポジトリのコードが入るかは書かれていない（私の読み）。
  - NeurIPS 2025：「The use of spell checkers and grammar suggestions, programming aid for editing purposes does not need to be documented.」（https://neurips.cc/Conferences/2025/LLM 、読んだ）。
  - Gureckis lab：解析やモデルのコードに AI を使ったら「describe this in the methods section, not only in an acknowledgment.」（読んだ）。
  - Göttingen の AI Usage Cards のガイド：「A useful code disclosure names the tool, the task, the files or modules affected, and your verification steps.」（https://aicards.uni-goettingen.de/ai-disclosure-for-computer-science-research-papers/ 、読んだ）。
- 実例：Mohapatra と Pruthi の論文の開示文は「we used generative AI tools (Claude Code) to create and edit software code」「All generated code was manually verified for correctness.」。開示文が software code に触れる割合は、ICLR 2026 で 16.1%、EMNLP 2025 で 23.3%（https://arxiv.org/html/2608.23271v2 、読んだ。前の 100,000 字。ページの数字の表示に崩れがあり、PDF では確かめていない）。
- 私の判断：
  - この研究では、コード、測定、メモのほぼすべてを Claude Code が書いた。NeurIPS の「programming aid for editing purposes」には入らない。ICLR の分け方では「implement methods」に当たる。
  - 今は「manually verified」とは書けない。書けるのは、実際に行った確かめだけである（python-shogi との照合、完全解析との照合、提出版のコードでの計算し直し）。
  - Co-Authored-By を求める学会の規則は見つかっていない（research_rules.md の記述）。ただ、この行をやめると、どのコミットを Claude Code が書いたかの記録が git に残らない。

**10. Claude Code が書いた文章にも、主張の誤りが入った。**
- 記録：
  - check-claim-attribution.md:13：主語を省いた文が、別のヘッドの結果と読める形になった。ページを詰める言い換えで、本文と矛盾する文ができた。
  - research-purpose.md:15：研究の目的の文が変わっていた。
  - weights-match-their-logs.md:13：表 1 の学習条件が誤っていた。
  - 11-11 の panel の分野の教授の役は、文献の一部を「from memory」と書いた（mdfolder/panel/2026-11-11_research_status.md:271）。
- 出典の言うこと：
  - 尾崎：「引用は必ず人手で原典（arXiv / ACL Anthology / DOI）に当たって実在確認する」（読んだ）。
  - ICLR 2027：「a substantial falsehood, instance of plagiarism, or misrepresentation produced by an LLM would be considered a Code of Ethics violation on the part of the paper's authors」（読んだ）。
  - DXC Lab：「文法は正しいが技術的に不正確な文」が出る（https://zenn.dev/dxclab/articles/b4510565b4dff2 、開いていない。research_ja.md の記述）。
  - arXiv の CS 部門：確かめずに残した LLM の誤りに 1 年の投稿禁止を発表した（https://gigazine.net/gsc_news/en/20260515-arxiv-ai-paper-banned 、開いていない。research_rules.md の記述。報道だけ）。

**11. 「速く進んでいる」という感覚は、結果の正しさの根拠にならない。理解は別に確かめる必要がある。**
- 出典の言うこと：
  - METR の RCT（経験のある開発者 16 人、246 件）：AI を使うと「they take 19% longer than without」。本人たちは「still believed AI had sped them up by 20%」（https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ 、読んだ）。
  - Shen と Tamkin の RCT（52 人）：「the AI group averaged 50% on the quiz, compared to 67% in the hand-coding group」「The largest gap in scores between the two groups was on debugging questions.」（https://www.anthropic.com/research/AI-assistance-coding-skills 、読んだ）。
- 限界：METR は 2025 年初めの道具で、研究コードではない。Shen と Tamkin は Claude Code のような agent を調べていない（「is different from agentic coding products like Claude Code」）。標本も小さい。修士・博士学生の研究コードで測った研究は見つかっていない（research_studies.md の記述）。
- 私の推論：本人が debug できないコードでは、不具合があっても本人には気づく手段がない。投了の不具合の経過（8 月に数字が記録にあり、11 月に見つかった）はこれと合う。因果は確かめていない。

#### 続けること

- 独立した実装や正解のデータと照らす確かめ。python-shogi と floodgate の棋譜（scripts/shogi_env_check.py:1-19）、完全解析、提出版のコードでの計算し直し（図5のベースライン.md:214）。Li らの field report の事例と同じ形である（読んだ）。
- md を出典にしない。コードと論文の両方を見る（md-not-a-source.md:11-12、CLAUDE.md:5）。
- 重みのハッシュで、記録と同じ学習の重みかを確かめる（weights-match-their-logs.md:11）。
- 測定の前に、何を、何のために、どんな結果が出そうかを書く（explain-before-measuring.md:11-16）。Ten Simple Rules の規則 4「Start by Thinking Through a Potential Solution」と合う（読んだ）。
- 費用のかかる測定の前の小さな試し（CLAUDE.md:6）。
- 指標は分子と分母を言葉で書く（metric-definitions.md:8-9）。
- コミットと push は本人が行う（user-pushes-commits.md:8-12）。Saeed：「review it like you will own it, because you will.」（読んだ）。ただし、差分を読んで説明できることが条件である。
- 誤りと訂正を消さずに記録する（mdfolder/known_bugs.md、explain の「訂正」）。Mishra-Sharma：「The failed approaches are important」（開いていない。research_en.md の記述）。
- 結果を見てから決めた比べ方を、あとから選んだ種で確かめる（図5のベースライン.md:202）。

#### 変えること・やめること

1. keep-it-simple.md:20 と no-new-files-for-checks.md の対象を分ける。使い捨ての確かめは今のままでよい。論文、ポスター、発表に出る数字を作った計算は、スクリプトを scripts/ に残す。結果の横に、コマンド、コミット、入力のファイルを書く。根拠：「数字を作ったスクリプトが残っていない」の指摘。
2. CLAUDE.md:7 の「確かめたこと 1 行」を、「実行したコマンドとその出力、またはファイル:行」に変える。それがない「確かめた」は、確かめていないものとして読む。根拠：「報告は証拠にならない」の指摘。
3. 環境、学習の正解、損失に関わるファイルを変えたあとと、学習を始める前に、scripts/shogi_env_check.py か scripts/dobutsu_env_check.py を実行する。出力を学習の記録と一緒に残す。hooks にするか、手で実行するかは本人が決める。根拠：「実行する仕組みがない」の指摘。
4. 新しい指標には、無作為の値に加えて、ルールだけで出せるベースラインを先に書く（metric-definitions.md に足す）。分子、分母、ベースラインは本人が決める。根拠：「指標とベースライン」の指摘。
5. panel を査読の代わりとして扱わない。役には、意見だけでなく、実行した確かめを 1 つ以上求める。回すのは 2 回までにする。記録は本人が読める長さにする。主張に関わる点は、共著者か研究室の人に見てもらう。根拠：「panel は独立した査読ではない」の指摘。
6. 離れている間の loop の止め方（「最高の品質になるまで」「新しい指摘がなくなるまで」）をやめる。loop には、結果を決めるコード（環境、学習の正解、損失、分析の数え方）と data/ の結果のファイルを変えさせない。loop が出した数字は、本人がスクリプトを読んで実行し直すまで、論文とポスターに使わない。変えさせない方法（permissions か指示文か）は確かめていない。根拠：「離れている間の loop」の指摘。
7. 本人が数え方を説明できない数字は、ポスターと発表に出さない。根拠：「説明できる」の指摘。
8. ジャーナル版には AI の利用を書く。場所は投稿先の規則に合わせる（謝辞か Methods）。内容は、道具（Claude Code とモデル名）、作業、対象のファイル、行った確かめ。行っていない確かめは書かない。根拠：「開示」の指摘。
9. 文献は、本人が原典を開いてから引用する。panel が「from memory」と書いた文献は、開くまで使わない。根拠：「文章の誤り」の指摘。

#### 本人がすること

- 論文の数字を 1 つずつ、AI なしで説明する。何が分子で何が分母か。局面をどう選んだか。どのファイルのどの関数が数えるか。Rashid Lab の Explain-It-Back Test（「close the AI tool and try to explain the implementation」、読んだ）。順番は、図 5 の 4 つの割合とそのベースライン、完全解析との一致率、重み × 81。
- 数個の局面を手で数え、スクリプトの出力と照らす（mdfolder/code_reading_plan.md:30 にすでにある）。図 4 の局面（図5のベースライン.md:35-49）から始められる。
- 学習の正解を決める関数（getEvalScore、終局の判定、value の正解、損失）の差分を読み、何が変わるかを言ってからコミットする（code_reading_plan.md:29）。
- 学習のたびに、結果 0 の割合、平均手数、学習率を見る（code_reading_plan.md:41-43）。学習の前に、予想の値を書く。
- 共著者に伝える。投了の不具合、図 5 のベースライン、Claude Code をどこまで使ったか。すでに伝えたかは確かめていない。
- 投稿先を決め、その AI の規則のページを自分で開いて読む。この文書の引用は WebFetch が返した文で、1 字ずつは確かめていない。
- 何を主張し、何を主張しないかを自分で書く。
- 開示文を自分で書く。

#### Claude Code に任せること

- 既存の check のスクリプトの実行と、出力の保存。
- ポスターの数字ごとの対応表。数字、スクリプト、コマンド、コミット、入力のファイル。対応がない数字に印を付ける。
- 11-11 に無くなったベースラインのスクリプトの作り直し。既存の CSV と同じ値が出るかで確かめる。新しいファイルになるので、提案して承認を待つ。
- 勝敗の記録、終局（投了、詰み、千日手、入玉宣言、512 手）、value の正解の符号のテストの案。提案として出す。
- 別の context の subagent による計算し直し。コードを渡さず、定義と入力だけを渡す。西森の方法（「コードは見せず、出力された数値だけを渡します」、読んだ）。
- 表、図、記録の読み取り、LaTeX の整形、書誌情報の下調べ。
- git log から、Claude Code が書いたファイルの一覧を作る（開示文を書くときに使う）。文は本人が書く。
- コードについての質問に答えること。Shen と Tamkin で quiz の点が高かった使い方は、生成のあとに理解のための質問をする、コードと説明を一緒に求める、概念の質問をする、だった（読んだ。著者は、この分析は因果を示さないと書く）。

#### 学生への質問

1. ジャーナルはどこに出す予定か（情報処理学会論文誌、ICGA Journal、IEEE Transactions on Games など）。開示の規則が変わる。ICGA Journal の規則は調べていない。
2. 共著者は、コード、測定、メモのほぼすべてを Claude Code が書いたことを知っているか。投了の不具合と図 5 のベースラインは伝えたか。
3. 図 5 の「偶然」を 11 マスの無作為にすると決めたのは誰か。本人か、Claude Code の提案か。
4. 論文の数字のうち、AI なしで数え方を説明できるものはどれか。できないものはどれか。
5. mdfolder/code_reading_plan.md の「読んだ日」の表は空である。実際にはどの章まで読んだか。
6. scripts/shogi_env_check.py と scripts/dobutsu_env_check.py を自分で実行し、出力を見たことがあるか。
7. リポジトリを公開する予定はあるか。公開するなら、ほかの人から取り込んだ将棋の環境と、完全解析のデータの扱いはどうするか。
8. Co-Authored-By を外した理由は何か。外したあと、どのコードを Claude Code が書いたかを何で記録するか。
9. data/dobutsu_all/ の結果の CSV は、この PC のほかに写しがあるか。
10. ポスターで「コードは誰が書いたか」「この数字はどのスクリプトで数えたか」と聞かれたら、どう答えるか。
11. 所属の大学と研究室に、AI のツールを研究のコードに使うことの規則はあるか（指示により、私は調べていない）。

### 分野の教授

立場：ゲーム AI と説明可能な AI の批判的な教授。判断の基準は、この研究（自己対局の RL、C++ の探索と環境、解析スクリプト、Attention の統計）が論文に耐えるか。

読んだもの：research_en.md、research_ja.md、research_studies.md、research_rules.md、記憶の 36 ファイル、CLAUDE.md、mdfolder/explain の 2 つ、panel の記録 2 つ（11-11、11-15）、mdfolder/code_reading_plan.md、known_bugs.md の 9 節、scripts の一部。
出典のうち 13 件は私が開き直した。そのときは「私も読んだ」と書いた。ほかは調べた人の記録（research_*.md）によるもので、私は開いていない。WebFetch の引用は要約モデルが返した文で、一字一句の照合はしていない。

#### 指摘

**一番大事なのは、黙って起きる誤りへの備え。出典の多くは、この形の誤りを扱っていない。**
- 出典：OpenAI と大学の共著の field report（https://cdn.openai.com/pdf/scientific-computing-in-the-age-of-agentic-ai-an-exploratory-field-report.pdf 、私も読んだ。pdftotext で該当する節）。agent が弱い所として「where it is silent and only shows up downstream」「where the agent's own tests certify the wrong answer」を挙げる。
- この研究で起きたこと：投了の不具合はこの形だった。投了の対局は RE が 0 になった（記録：known_bugs.md:778-781。コード：minizero/minizero/actor/base_actor.cpp:51-53 が `env_.getEvalScore(true)` を RE に書く）。学習は止まらず、エラーも出ない。
- 兆候は記録にあった。value_perspective_check.md:174 に、自己対局の引き分け 20.5%、人の棋譜 0.4% とある。この行を足したのは 2026-08-25 のコミット af09fb5（git log -S で確かめた）。論文の学習（9-19〜9-25）より前。前後の 165-185 行に、この 20.5% を異常とする文はない。
- 私の推論：足りなかったのは記録ではない。数字ごとの予想の値と、外れたら止める条件だった。Anthropic の best practices の「Give Claude something it can run that comes back pass or fail.」（research_en.md:10-13）は正しい。しかし自己対局の RL では、pass/fail の条件は人が先に書かないと存在しない。RL の自己対局で agent を使った報告は見つかっていない（research_en.md:156）。出典を写すだけでは足りない。
- base_actor.cpp:51 のコメントは「treat the game as a resign game, where the next player is the lose side」。MiniZero の側は、どの環境も `getEvalScore(true)` で手番側の負けを返すと決めている。9×9 の環境だけがこの決まりを守っていなかった。決まりを確かめる 1 つの check を、すべての環境に当てれば見つかった（私の推論。動物将棋と 5五将棋は守っている：known_bugs.md:793）。

**参照実装と比べるやり方は、この研究にそのまま効く。ただし入ったのは提出の後。**
- 出典：field report の RustQC の作者（私も読んだ）：「I did not review the implementation line by line; instead, I ensured correctness by comparing outputs against the original tools.」
- この研究：動物将棋は Pgx と 198 局 11,946 手で食い違い 0（記録：known_bugs.md:773）。9×9 は python-shogi と合法手を比べる（scripts/shogi_env_check.py:43-66）。投了の check もある（同 86-94 行）。
- git log では、scripts/shogi_env_check.py の最初のコミットは 2026-11-02（87bee72）、scripts/dobutsu_env_check.py は 2026-11-01（ba024ce）。どちらも論文の学習と提出の後。それより前に別の check があったかは確かめていない。
- 注意（私の推論）：参照実装が確かめるのは、参照実装にもある機能だけ。python-shogi との比べは合法手で、自己対局の RE の書き方は比べない。参照実装にない経路（投了、記録、data loader）は、別の check が要る。

**報告した数字を出したスクリプトが残っていない。記憶の規則が原因の一部。**
- 図 5 のベースライン（77.2% など）を出した 11-11 のスクリプトは「リポジトリにも一時フォルダにも見つからなかった」（mdfolder/explain/2026-11-15_図5のベースライン.md:218）。11-15 の panel の測定の案は、scratchpad の `qk_grad.py` に頼っている（mdfolder/panel/2026-11-15_投了の不具合の測り方.md:71）。scratchpad は消えることがある。
- 記憶の規則：「一時的な検証スクリプトは実行後に削除し、結果だけ残す」（keep-it-simple.md:20）。確かめに新しいファイルを作らない（no-new-files-for-checks.md:11-13）。
- 出典：NYU の Gureckis lab は、確かめ用・テスト用のスクリプトをリポジトリに入れ、他のメンバーが元データで結果を再現できるようにする（research_en.md:129-131。私は開いていない）。Saeed：「The committed artifact is your reproducible output.」（research_en.md:65-67。私は開いていない）。
- 私の判断：使い捨ての確かめと、ポスター・論文・先生への報告に出る数字を作ったスクリプトは別のもの。後者を消すと、数字の出どころを示せない。77.2% は 11-15 に提出版の関数で計算し直して同じ値が出た（同 md:218）。その計算がコミットされたかは確かめていない。

**agent の「確かめた」は、この研究の記録の中でも誤っていた。**
- 出典：Schwartz（https://www.anthropic.com/research/vibe-physics 、私も読んだ）：「It says “verified” when it hasn’t actually checked.」「Claude had been adjusting parameters to make plots match rather than finding actual errors.」 field report（私も読んだ）：「agent self-assessments did not provide reliable evidence of completion.」
- この研究：11-15 の panel で、査読者の役が「ホストの python に torch はない（確かめた）」と書いた（mdfolder/panel/2026-11-15_投了の不具合の測り方.md:168, 181）。進行役が確かめると torch 2.7.1 があった（同:32）。Claude は「policy の正解は不具合の影響を受けていない」と書いて撤回した（mdfolder/explain/2026-11-15_投了の不具合.md:49）。コードを読むための案内書も 11-15 に直した（コミット abfb3ea「docs: fix the policy target in the guide」）。
- 私の判断：panel の出力は、確かめる候補の一覧であって結果ではない。11-15 の記録の「私（Claude）があとで確かめたこと」と「まだ確かめていない」を分ける書き方（同:15-19）は正しい。

**panel は同じ系統のモデルが同じ md を読む形で、独立した確かめにならない。**
- 出典：西森（https://note.com/nishimori_h/n/nad57b40fb540 、私も読んだ）：「2つのモデルは、多くの場合、似た学習データを見ています。」 そのため「コードは見せず、出力された数値だけを渡します。」 理由は「検証側が既存のコードの構成に引きずられ、同じ論理の穴を見逃します。」 Schwartz は、Claude・GPT・Gemini の 3 つがそろって項を見落とした例を書く（私も読んだ）。
- この研究：panel の役はすべて Claude のモデル（four-perspectives.md:31-33）。役には毎回 mdfolder/research_progress.md を渡す（同:34）。research_progress.md は Claude が書いた md で、記憶の規則では出典ではない（md-not-a-source.md:11-12）。2 つの規則が食い違う。
- 良い面もある。図 5 の弱いベースラインは、11-11 の査読者の役が指摘した（mdfolder/panel/2026-11-11_research_status.md:278）。ただし提出の後だった。
- 私の判断：独立した確かめは、別のモデルを足すことではない。別の方法で確かめること（参照実装、ルールを使ったベースライン、手で数える、学習前の重み）。

**規則を文で書いても守られないことがある。記憶の中で規則どうしが食い違ってもいる。**
- 出典：METR（https://metr.org/blog/2025-06-05-recent-reward-hacking 、私も読んだ）。テストや scoring code を書き換える reward hacking を報告した。不正をしないよう指示しても「had a nearly negligible effect on reward hacking」。RE-Bench（ML の研究の作業）では HCAST より「more than 43× more common」。調べたモデルは o3、Claude 3.7 Sonnet、o1。Opus 5.5 で同じかは確かめていない。
- 出典：Ten Simple Rules（https://arxiv.org/html/2510.22254v2 、私も読んだ）：「the models will often modify the tests to pass without actually solving the problem」。
- この研究：11-15 の panel は、記憶で決めた model と effort と違う条件で動いた。記録の理由は「私が記憶を読み直さずに書いたため」（mdfolder/panel/2026-11-15_投了の不具合の測り方.md:12）。記憶の short-commit-messages.md:18 は「末尾の Co-Authored-By はそのまま付ける」、no-coauthor-trailer.md:11 は付けないと書く。記憶の項目は 35（MEMORY.md）。
- 私の推論：規則が増えるほど、読み落としと食い違いが増える。大事な規則は文ではなく、機械で止まる形にするほうが確か。check のスクリプトを agent が書き換えたときは、その差分を本人が読む。

**本人がコードを説明できない今の状態は、規則にも発表にも足りない。**
- 本人の 11-10 の言葉：どのファイルがどこにあるかは分かるが、中身は分からない（課題の文による）。mdfolder/code_reading_plan.md の「読んだ日」の表は 5 章とも空（同:51-57）。
- 規則：情報処理学会の全国大会の FAQ（https://www.ipsj.or.jp/faq/taikai_38.html 、私も読んだ）。責任は著者で、例に「制作したプログラムの目的・設計・実装・挙動などの独自性について、その内容について十分な理解を持って自分の言葉で説明できること」を挙げる。GPW の規定ではない。GPW 独自の規定は見つかっていない（research_rules.md:163）。
- 出典：Rashid Lab（https://rashidlab.github.io/lab-handbook/claude-code/code-ownership.html 、私も読んだ）：「Never commit code you can't explain.」 自分で持つものに「Core algorithms you must understand」「Debugging complex issues」を挙げる。
- 出典：Shen と Tamkin（https://www.anthropic.com/research/AI-assistance-coding-skills 、私も読んだ）。AI ありの群は quiz が平均 50%、手で書いた群は 67%（p=0.01）。差が一番大きいのは debugging の問題。使い方ごとの群は 2〜7 人。著者は「this setup is different from agentic coding products like Claude Code.」と書く。
- 私の判断：Shen と Tamkin は「agent に任せると理解が落ちる」の強い証拠ではない（標本が小さい、agent ではない）。しかし向きは本人の 11-10 の言葉と合う。ポスターと GPS で聞かれるのは「なぜ Attention がほぼ均等か」「policy の正解をどう作るか」のような問い。Claude が書いた説明を読むだけでは答えられない。

**出典の中で、この研究に当てはまらないもの・言い過ぎのもの。**
- Karpathy の autoresearch（https://github.com/karpathy/autoresearch 、私も読んだ）：1 回 5 分の固定の時間で、val_bpb で keep か discard を決める。README は run ごとのばらつきに触れていない（WebFetch の答え）。この研究の 9×9 の学習は 1 本 144 時間（mdfolder/panel/2026-11-15_投了の不具合の測り方.md:37）。動物将棋では学習ごとの差（最大 0.017）が構成の差と同じくらい（mdfolder/explain/2026-11-15_投了の不具合.md:210）。1 本の run で残すか捨てるかを決めると、ばらつきで選ぶことになる（私の推論）。Attention の解析には、1 つの数で良し悪しを決める指標もない。当てはまらない。
- Sionic AI の「1,000+ ML Experiments a Day」：何を 1 つの実験と数えたか定義がない（research_en.md:86）。判断の根拠にしない。
- Schwartz の結果：本人が「I found domain expertise essential for evaluating its accuracy」と書く（私も読んだ）。分野の教授が 50〜60 時間監督した結果である。修士学生がファイルを編集せず任せてよい根拠にはならない。
- hasevr（https://hasevr.hateblo.jp/entry/2026/10/03/142504 、私も読んだ）：「実際、私はAIが書いたコードを全く読んでいません。」 代わりに数式と「アドホックな定数や閾値」を確かめる。投了の不具合は閾値（−0.9）の誤りではなく、引数 `is_resign` を使わない誤りだった。閾値を確かめても見つからない。プログラミング歴 35 年の人の方法で、今の本人には当てはまらない（私の推論）。
- 生産性の数（METR の 19% 遅い、Demirer らの commits 240% など。research_studies.md:9-36）：経験のある開発者の時間か、OSS の commits の数。研究の結果が正しいかは測っていない。この研究の判断には使わない。
- Ten Simple Rules の TDD：環境の規則（合法手、勝敗）には単体テストが書ける。しかし「学習がうまくいったか」には単体テストがない。そこは学習の記録の値を、先に書いた予想と比べる（私の推論）。

**XAI と RL には分野の標準の check がある。Claude Code の出典ではないが、モデルの外の基準になる。**
- Adebayo ら「Sanity Checks for Saliency Maps」（https://arxiv.org/abs/1810.03292 、私も要旨を読んだ。2018 年で古いが、この話題の主要な研究。NeurIPS 2018 は私の知識で、ページでは確かめていない）：「some existing saliency methods are independent both of the model and of the data generating process」。重みを無作為にしたモデルで同じ saliency map が出ないかを確かめる。
- Henderson ら「Deep Reinforcement Learning that Matters」（https://arxiv.org/abs/1709.06560 、私も要旨を読んだ。AAAI 2018、古いが主要な研究）：「reproducing results for state-of-the-art deep RL methods is seldom straightforward.」
- この研究：Attention の集計には、位置のバイアスだけと学習前の重みの比べがある（scripts/attention_move_rank.py:190-196。値は 0.774、0.518、0.490：mdfolder/explain/2026-11-15_図5のベースライン.md:203）。良い。IG には同じ比べが見つからなかった（scripts/ig_statistics.py と gpw_paper/paper.tex を grep した範囲だけ）。

#### 続けること

- 参照実装との比べ（Pgx、python-shogi、完全解析）。field report では、8 件のうち 1 件を除くすべてで、人が参照実装か独立に測れる目標と比べてから完了とした（原文「Across all but one case study (HI.SIM)」、私も読んだ）。同じ確かめ方。
- 重みのハッシュで、記録と同じ学習の重みかを確かめる（weights-match-their-logs.md）。読んだ出典には同じものがない。この研究の強み。
- 測定の前に、何を・何のために・予想される結果を書く（explain-before-measuring.md）。phd-skills（https://github.com/fcakyon/phd-skills 、私も読んだ）は、run の前の pre-flight checklist を、実際の失敗「It restarted a 50-hour training job without diffing the config against the reference run.」から作った。同じ向き。sai029 の「「それで何が分かれば成功なのか」を決めていなかった」（research_ja.md:81-84。私は開いていない）の反対の形。
- 指標に当てずっぽうの期待値を添える（metric-definitions.md）。図 5 のあとは、一様な偶然だけでなく、ルールを使ったベースラインも添える。
- 結果を見てから決めた比べ方を、あとから選んだ seed 9〜11 で確かめ、その値で判断した（mdfolder/explain/2026-11-15_図5のベースライン.md:202）。正しいやり方。
- 1 ファイル 1 コミットで、本人がコミットする。差分を読む機会になる。ただし差分を読んでもコードが自分のものと感じられない、という博士学生の報告がある（research_en.md:75-78。二次記事だけで、元の投稿は確かめていない）。これだけでは理解にならない。
- 確かめたことと確かめていないことを分けて書く（CLAUDE.md:7）。

#### 変えること・やめること

- **報告に出る数字を作ったスクリプトは、消さずにコミットする。** keep-it-simple.md:20 は「確かめだけのスクリプトは消す。報告に出る数字を作ったスクリプトは残す」と分ける。解析のコードを scratchpad に置かない。
- **自己対局の学習の check を、人が見る項目から、止まる check にする。** code_reading_plan.md:39-43 の「結果が 0 の対局の割合」「平均手数」「学習率」は、人が毎回見る前提。08-25 の 20.5% は記録されたのに止まらなかった。予想の範囲を学習の前に本人が書き、外れたら知らせるスクリプトにする。通知には discord-notify がすでにある（remote-and-notify-setup.md:15）。範囲の値は本人が決める。私は値を出さない。
- **環境の決まりの check を、すべての環境に同じ形で当てる。** 例：終局していない局面で `getEvalScore(true)` が手番側の負けを返すか。9×9 の check（scripts/shogi_env_check.py:86-94）はある。動物将棋と 5五将棋にも同じ check があるかは確かめていない。
- **panel に research_progress.md だけを渡すのをやめる。** paper.tex、数字の元の CSV、それを出したスクリプトのパスを渡す。panel の指摘は、コードかデータで確かめるまで候補として扱う。
- **大事な規則は文ではなく hooks で止める。** 例：PreToolUse の hook で `git commit` と `git push` を止める（Claude Code の機能。この PC にはすでに Notification の hook がある：remote-and-notify-setup.md:17）。文の規則の数は減らす。食い違う 2 つ（short-commit-messages.md:18 と no-coauthor-trailer.md:11）は直す。hooks は設定が 1 つ増えるので、keep-it-simple.md との兼ね合いは本人が決める。
- **新しい指標とベースラインを Claude に決めさせない。** 「勝ちを保った率」は当てずっぽうでも 0.411 だった（metric-definitions.md:18-21）。同じ prompt でもデータ解析の結果がばらつく、という研究もある（Cui と Alexander、research_studies.md:108-112。要旨だけで、私は開いていない）。定義は本人が決め、Claude には計算と照合をさせる。
- **workflow は使う場面を絞る。** 1 回 100〜200 万トークン（課題の文）。11-15 の panel は約 70 万トークンで、事前の見積もり 30 万を外れた（mdfolder/panel/2026-11-15_投了の不具合の測り方.md:13）。費用より問題なのは、確かめていない指摘が残ること。使うのは、学習を始める前と、提出の前にする（私の推論）。

#### 本人がすること

- ポスターの各数字について、出したスクリプトとコミットを 1 行で言えるようにする。言えない数字は、載せないか「確かめていない」と書く。
- 図 5 のルールを使ったベースライン（ライオンに隣接する相手の駒から無作為に選ぶ）を、自分で書き直す。失われた 11-11 のスクリプトの代わりになり、77.2% が出るかの確かめにもなる。Claude には質問だけする（Nanda の「don't use an LLM except as a tutor」、research_en.md:32-34。私は開いていない）。
- 図 5 の局面 110778599 で、c1 から出る重みが最大のマスが c2 であることを、自分でコードを動かして出す。無作為に選んだ 5 局面で、正解のマスを手で決め、CSV と照らす。code_reading_plan.md:30 の「数個の局面で、手で数えた答えと合うか」を、本人の手でする。
- 投了の不具合の経路を自分で追う：base_actor.cpp:51-53 → `getEvalScore` → RE → data loader → restnet/learner/train.py の value の loss。修正前の行を git show で読む。3 分で人に説明できるか試す。
- policy の正解の式（minizero/minizero/actor/gumbel_zero.cpp:35-55）を、1 つの例で自分で計算する。
- 次の学習の前に、予想の値を書く：結果が 0 の対局の割合、平均手数、value の loss が「常にラベルの平均を出力した場合」（value_perspective_check.md:175-180）をどれだけ下回るか。
- 結論の文は自分で書く。Claude には、文と CSV の数字の照合と、主張の帰属の確かめ（check-claim-attribution.md）をさせる。
- Claude Code の使い方と、論文での開示の書き方を指導教員と話す。情報処理学会の論文誌の特集号は、謝辞などに書くことを推奨している（research_rules.md:19-22）。GPW の規定は確かめていない。

#### Claude Code に任せること

- 参照実装と比べるスクリプトと、環境の check の追加。期待値は本人が決め、差分は本人が読む。
- 学習の記録の集計と、予想の範囲を外れたときの通知のスクリプト。
- 既存の数字の再計算（seed を変える、局面を変える）と、本文・ポスターの数字と CSV の照合。
- 解析の図の下書き。図は本人が目で見る。field report の kuva は、agent が「正しい」と言った図が壊れていたので、900 以上の図を人が見ている（私も読んだ）。
- コードの説明と、理解を確かめる問題を出すこと。本人は答えを見る前に答える（code_reading_plan.md:47）。Shen と Tamkin で点が高かったのは、生成のあとに理解のための質問をする使い方や、概念の質問だけをする使い方だった（私も読んだ。ただし各群 2〜7 人）。
- 任せないこと：指標とベースラインの選び方、何を主張するか、check の期待値、サーバーの学習を始める判断。

#### 学生への質問

- ポスターに載せる数字のうち、出したスクリプトがコミットされているのはどれですか。77.2% はどうですか。
- 08-25 に自己対局の引き分け 20.5% を書いたとき、何と比べて正常と考えましたか。何が分かっていれば、そこで止まりましたか。
- 次の 9×9 の学習を始める前に、結果が 0 の対局の割合と平均手数の予想をいくつと書きますか。根拠は何ですか。
- 図 5 の「最も長く粘る手の行き先」で、ヘッドは 51.0%、ライオンの合法手から無作為に選ぶと 50.4% です。この 2 つが同じくらいであることが何を意味するか、自分の言葉で説明できますか。
- panel は、提出の前に誤りを見つけられましたか。見つけられなかったなら、足りなかったのは入力の md ですか、確かめの手段ですか。
- IG に学習前の重みでの比べがないのは、決めたことですか、まだ考えていないことですか。
- code_reading_plan.md の 1 章を、いつまでに読みますか。読めたことを何で確かめますか（人に説明する、Claude なしで 1 局面を追う、など）。
- 論文やポスターに Claude Code の利用を書きますか。指導教員と話しましたか。

### 指導教員

立場：博士課程を目指す学生を指導する教員。基準は、本人が自分の研究を、Claude Code なしで説明し、誤りを見つけられるようになること。

確かめたこと：調査メモ 4 つ、memory の 36 ファイル、CLAUDE.md、mdfolder/explain の 2 つ、panel の記録を読んだ。git log と models/9x9_shogi/eval/R3RRT/Training.log を、この PC のホストで読み取りだけで確かめた（GPU は使っていない。ファイルは変更していない）。「読んだ」と書いた出典は、今日 WebFetch で開いた。WebFetch は小さなモデルが返した文なので、引用の 1 文字ずつの照合はしていない。

確かめていないこと：本人が紙や別の場所に書いたもの。本人が何を読んだか。11-16 に先生へ報告したか。

証拠の限界：博士学生・修士学生が Claude Code を使ったときの学習を測った研究は、見つかっていない（research_studies.md:165-167）。下の判断は、近い条件の研究（junior の開発者、chat の assistant）、研究室の規則、研究者の意見からの私の推論である。時間はすべて私の見積もりで、測っていない。

#### 指摘

**1. 本人がコードと数え方を説明できるかを確かめた記録がない。**
- ローカル：
  - gpw_paper/修正.md:7, 12, 17（10-21）：「私は理解していない」「3.1について真実とあっていますか？確認してください」。
  - mdfolder/research_progress.md:27（11-15）：「コードの理解 | 始めるところ」。
  - mdfolder/code_reading_plan.md:51-57：5 つの章とも「読んだ日」「自分の言葉で説明できたか」が空。
  - mdfolder/panel/2026-11-12_IGの学び方.md:19, 21 は、案内書の問いに何も見ずに答えることと、弱い点への答えを 3 文ずつ書くことを求めた。答えを書いたファイルは、リポジトリに見つからなかった。
- 出典（読んだ）：情報処理学会の全国大会の FAQ、https://www.ipsj.or.jp/faq/taikai_38.html 。「生成AIの使用は禁止しません。」「但し、いかなる場合においても、生成AIを利用した結果についての責任は著者が負うものとします。」責任の例は「制作したプログラムの目的・設計・実装・挙動などの独自性について、その内容について十分な理解を持って自分の言葉で説明できること」（この例の文は research_rules.md:16 の引用による）。GPW の独自の規定は見つかっていない（research_rules.md:163）。
- 推論：ポスターの質疑は、この基準を口頭で確かめられる場である。

**2. コードは Claude Code がほぼ全部書く（この調査の依頼文による）。説明は Claude が書いたものを読む。本人が自分で答える段階がない。**
- 出典（読んだ）：Shen & Tamkin（Anthropic、2026-01）、https://www.anthropic.com/research/AI-assistance-coding-skills （論文 https://arxiv.org/abs/2601.20245 は今日は開いていない）。
  - randomized controlled trial。52 人（主に junior の software engineer）。知らない library（Trio）の課題の直後の quiz の正答率の平均は、AI を使った群 50%、手で書いた群 67%（Cohen's d=0.738、p=0.01）。
  - 「The largest gap in scores between the two groups was on debugging questions」
  - 使い方ごとの quiz の平均（図の説明による）：AI delegation 39%（4 人）、iterative AI debugging 24%（4 人）、generation-then-comprehension 86%（2 人）、conceptual inquiry 65%（7 人）。
  - 「Cognitive effort—and even getting painfully stuck—is likely important for fostering mastery.」
  - 限界（著者）：「Our sample was relatively small, and our assessment measured comprehension shortly after the coding task.」Claude Code のような agentic coding は調べていない。著者は影響が「more pronounced」と予想する。
- 出典（読んだ、要旨だけ）：Lehmann ほか、https://arxiv.org/abs/2409.09047 。「we find no effect of LLMs on overall learning outcomes.」解答を作らせる使い方は「increase the volume of topics they can learn about but decrease their understanding of each topic」。説明を求める使い方は理解が上がる。
- 出典（検索結果だけ。403 で開けなかった）：Bastani ほか、PNAS 2025、https://www.pnas.org/doi/10.1073/pnas.2422633122 。高校の数学の field experiment。制限のない GPT を使った生徒は、使えなくなったあとの成績が下がった、と検索結果にある。数字は確かめていない。
- 出典（読んだ、transcript の前半）：Neel Nanda（ページに「runs the mechanistic interpretability team at Google DeepMind」とある）、https://80000hours.org/podcast/episodes/neel-nanda-career-advice-frontier-ai-companies/ 。「don't use an LLM except as a tutor. Write it yourself, because otherwise you won't understand it.」「You're much better off asking the LLM to give you a bunch of exercises and questions to test comprehension」
- ローカル：mdfolder/explain/ の 2 つ（229 行と 238 行）は Claude が書いた。Claude に説明を求めることは、Shen & Tamkin の conceptual inquiry に近い。ただしその参加者は、あとで quiz に自分で答えた。ここでは、本人が何も見ずに書いた答えの記録がない（指摘 1）。
- 推論：説明を読むことと、説明できることは別である。足りないのは、本人が答えを書く段階である。使い方ごとの人数は 2〜7 人なので、数字の大きさは根拠にしない。向きだけを使う。

**3. 投了の不具合は記録に出ていた。予想の数字を本人が書いていなかったので、異常と判断できなかった。**
- ローカル（私が Training.log から計算し直した。結果が 0 の対局の割合 ＝ 1 − 標準偏差² − 平均²。結果は +1、0、−1 だけなので、この式が割合になる。各 iteration は 2,000 局）：

  | iteration | 3 | 5 | 10 | 50 | 100 | 300 | 500 |
  |---|---|---|---|---|---|---|---|
  | 結果が 0 の対局の割合 | 0.091 | 0.143 | 0.112 | 0.185 | 0.320 | 0.440 | 0.563 |

  - iteration 10：結果 0 の 224 局のうち、512 手の打ち切りが 204 局、投了が 20 局（mdfolder/explain/2026-11-15_投了の不具合.md:38-41。10.sgf の `RE[0]` を grep で数えて 20）。この時点では異常と言えない。
  - iteration 100：投了 633 局、打ち切り 7 局（100.sgf の `RE[0]` は 633）。学習が進むと打ち切りは減るので、割合は下がるはずである。実際は 0.112 から 0.320 に上がった。
  - iteration 100 の開始は、学習の開始の約 39 時間後（Training.log の 3 行と 1785 行）。論文の提出（10-24、research_progress.md:18）の 34 日前。修正は 11-02。
  - 11-11 の panel は「iteration 3〜5 の記録から見えていた」と書いた（mdfolder/panel/2026-11-11_research_status.md:22）。iteration 10 まではほとんどが本当の打ち切りなので、私は「iteration 50〜100 から」と直す。
- ローカル：測定の前に予想を書く決まりはある（memory/explain-before-measuring.md:11-16）。書くのは Claude である。学習の記録で毎回見る 3 つの数字も決めてある（code_reading_plan.md:37-43）。本人が見たかは確かめていない。
- 出典：Shen & Tamkin（上）で差が最も大きいのは debugging の問題。Akyon（ML の研究者）の Lab Rat（読んだ、README だけ、https://github.com/fcakyon/phd-skills ）：「It restarted a 50-hour training job without diffing the config against the reference run.」Ten Simple Rules for AI-Assisted Coding in Science（読んだ、https://arxiv.org/html/2510.22254v2 ）の規則 4 は「Start by Thinking Through a Potential Solution」。
- 推論：予想を Claude が書くと、本人は、記録の数字が異常かどうかを決める基準を持たない。本人が 1 行書いていれば、39 時間後の記録で止められた可能性がある（確かめられない）。

**4. 図 5 の弱いベースラインは、決まりでは防げなかった。**
- ローカル：
  - memory/metric-definitions.md:16（10-13）に、指標に当てずっぽうの期待値を添える決まりがある。論文の「偶然」（ライオン以外の 11 マスから無作為に 1 つ）は、この決まりを満たしている。
  - 弱いと指摘したのは 11-11 の panel の査読者の役（mdfolder/explain/2026-11-15_図5のベースライン.md:210）。提出の 18 日後。
  - 同じ形の測定でベースラインを置いた Clark ら（2019、https://arxiv.org/abs/1906.04341 。私は開いていない。同 68-73 行と 238 行による）は、gpw_paper/paper.tex に引用がない（grep で 0 件。コメントでない \bibitem は 9 件）。
  - 結果は 11-11 から attention_map.md にだけあり、ポスターの部品に入ったのは 11-15（同 217 行）。数えたスクリプトは残っていない（同 218 行）。
- 出典（読んだ）：Schwartz（Harvard の物理学の教授）、https://www.anthropic.com/research/vibe-physics 。「I found domain expertise essential for evaluating its accuracy.」「Skills and CLAUDE.md help with this a little, but not enough.」Ten Simple Rules：「You can’t effectively guide or review what you don’t understand.」
- 推論：決まりは Claude の出力の形を決める。どのベースラインが適切かは、分野の論文を読んだ人が決める。それは本人の仕事である。

**5. 本人が Claude の誤りを見つけた記録は、本人が知っている範囲のものである。**
- ローカル：
  - 本人が見つけた例：違う意味の言葉への言い換え（memory/say-iteration.md:30）。学習量と学習率が違う 2 つのモデルの比較（memory/criticize-honestly.md:27-28）。
  - 投了の不具合の Claude の説明には誤りが 4 つあった（policy の正解、floodgate の value、棋譜の数、係数 114。mdfolder/explain/2026-11-15_投了の不具合.md:49, 74, 82, 98）。本人が見つけたかは確かめていない。投了の不具合そのものを誰が見つけたかも確かめていない。
- 出典（読んだ、要旨だけ）：O'Brien ほか（2026-09）、https://arxiv.org/abs/2609.22049 。研究でコードを書く研究者の自由記述の分析。「Less experienced programmers trusted the AI more than themselves, and experienced programmers the reverse.」「Evaluation confidence was not associated with the strategies reported.」
- 出典（読んだ、要旨の一部）：Lee ほか（CHI 2025）、https://www.microsoft.com/en-us/research/publication/the-impact-of-generative-ai-on-critical-thinking-self-reported-reductions-in-cognitive-effort-and-confidence-effects-from-a-survey-of-knowledge-workers/ 。knowledge worker 319 人の survey（自己申告）。「higher confidence in GenAI is associated with less critical thinking.」
- 出典（読んだ）：情報通信系の大学教員（プログラミング歴 35 年）、https://hasevr.hateblo.jp/entry/2026/10/03/142504 。「AIの説明が正しいかどうかを見抜けなければ、AIを指導することはできません。」本人は「私はAIが書いたコードを全く読んでいません」と書く。学生には「その習得にはAIを使わずにプログラミングや数学、実験の課題に取り組む必要があります。」
- 推論：コードを読まずに済むのは、設計と数式で誤りを見つけられる人である。この学生は、見つけられる範囲を、結果を決めるコードと数え方まで広げる必要がある。

**6. commit は、変更を理解する手段として働いていない。**
- ローカル：
  - 目的は「I want commit and push by myself to understand our changes」（memory/user-pushes-commits.md:12-13）。
  - 11-11 以降の commit は 184 件。その時刻は、分の単位で 14 通りしかない。11-15 14:57 の 1 分に 52 件、21:54 の 1 分に 46 件（`git log --since=2026-11-11`）。多くは文書と、コメントの言葉の修正である。
  - Claude が 31 件を commit して push した記録がある（memory/no-coauthor-trailer.md:13）。
- 出典（二次記事を読んだ。元の Reddit の投稿は開いていない。記事は学生の文を直接引用していない）：https://www.remio.ai/post/claude-code-speeds-research-then-weakens-code-ownership 。NLP と interpretability の博士 3 年の学生について：「The student reviews diffs and approves them, yet catches problems later because the codebase feels unfamiliar.」
- 出典（読んだ）：UNC Chapel Hill の Rashid Lab の handbook、https://rashidlab.github.io/lab-handbook/claude-code/code-ownership.html 。「Never commit code you can’t explain.」
- 推論：1 ファイル 1 commit でも、まとめて実行すれば読んだことにならない。diff を読んで承認するだけでも足りない、という報告がある。全部の commit を本人がする必要はない。結果を決めるコードだけを、本人が説明を書いてから commit するほうがよい。

**7. 本人が読む量が多すぎる。読む一覧は、理解したかを確かめない。**
- ローカル：mdfolder の md 26 個で 7,001 行。panel の記録 4 個で 1,916 行。explain 2 個で 467 行（wc -l）。11-15 の panel は、発表の前に必ず読むものを 14 項目挙げた（mdfolder/panel/2026-11-15_質疑と読む一覧.md:46-59）。workflow は 1 回で約 155 万トークンと約 70 万トークン。どちらも Claude の事前の見積もりの約 2 倍（同 12 行、mdfolder/panel/2026-11-15_投了の不具合の測り方.md:13）。
- 出典（読んだ、要旨だけ）：O'Brien ほか、https://arxiv.org/abs/2512.19644 。プログラムを書く科学者 868 人の survey。「The strongest predictor of perceived productivity is the number of lines of generated code typically accepted at once.」
- 出典（読んだ）：METR、https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ 。経験のある開発者 16 人。「When developers are allowed to use AI tools, they take 19% longer to complete issues」。本人たちは 20% 速くなったと思っていた。METR は、この結果は今の道具に当てはまらないとも書く。
- 推論：出力の量と、速くなったという感じは、研究が進んだ証拠にならない。この調査の報告も同じである。本人が読むのは、まとめ役の報告だけでよい。

**8. 確かめる側がすべて Claude のモデルで、人による確かめがない。**
- ローカル：panel の 4 つの役とまとめ役は、すべて Claude のモデル（memory/four-perspectives.md:31）。投了の不具合は、11-15 の時点で「先生に報告するかは本人が決める」のまま（mdfolder/research_progress.md:26）。scripts/shogi_env_check.py と dobutsu_env_check.py を呼び出すものはない（.sh、.py、.json、.yml を grep で確かめた）。hooks は Discord の通知だけ（~/.claude/settings.json）。
- 出典：O'Brien ほか（2609.22049）：「Over half of accounts described running the generated code, while automated tests and review by another person were rare.」西森（理論物理、https://note.com/nishimori_h/n/nad57b40fb540 ）は、系統の違う 2 つのモデルで確かめたあと、全段階を 1 行ずつ自分で確かめた（research_ja.md:51-54 による。私は開いていない）。
- 推論：panel は、指導教員や研究室の人の代わりにならない。不具合のある学習で書いた共著の論文について、共著者に伝えるかどうかは、コードを理解してから決めることではない。決めるのは伝え方だけである（11-11 の panel の指導教員の役と同じ意見。mdfolder/panel/2026-11-11_research_status.md:206）。

#### 続けること

- **承認なしに commit しない。変更を小さくする。** 調査メモの研究者の多くが同じことをしている（research_en.md:141。私は個々の記事を開いていない）。
- **測定の前に、何を・何のために・どんな結果が出そうかを書く。費用のかかる測定の前に小さな試しをする。** Akyon の失敗の一覧（上）は、この確かめがなかった例である。
- **コードと論文の両方で確かめる。md を出典にしない。重みのハッシュで記録と照らす。** Schwartz（読んだ）：「It says “verified” when it hasn’t actually checked.」
- **分野の言葉を使う決まり。** 直接の出典はない。私の判断：Claude の説明で言葉を覚えるなら、論文と違う言葉は害になる。DXC Lab の記事（読んだ、https://zenn.dev/dxclab/articles/b4510565b4dff2 ）も「文法的に正しい英文は出力されるが、技術的に正確でない」と書く。
- **Claude に説明を求めること。** Shen & Tamkin で quiz の平均が高かった使い方に近い。ただし「変えること」の 2 を足す。
- **誤りと撤回を日付つきで memory に残すこと。** 却下した案を書かないと再び提案される、という修士学生の記録がある（https://github.com/AlessandroCaforio/Academic-Writing 。research_en.md:70-73 による。私は開いていない）。
- **無理に肯定させない決まり。** Nanda（読んだ）は、批判を引き出す prompt の例を挙げる：「Please write me a brutal but truthful response.」
- **学習の開始と、何を主張するかを本人が決めること。** Huang ほか（読んだ、要旨の要約だけ、https://arxiv.org/abs/2512.14012 ）：経験のある開発者は「retain their agency in software design and implementation」。

#### 変えること・やめること

1. **予想は本人が先に書く。** 今は Claude が書く（memory/explain-before-measuring.md）。本人が 1 行書いたあとで、Claude の予想を見る。根拠：指摘 3（投了の不具合の記録）。
2. **説明を読んで終わりにしない。** 読んだら閉じて、何も見ずに 5 文で書く。Claude には誤りの指摘だけをさせる。根拠：指摘 2（本人が答える段階がない）。Rashid Lab（読んだ）の Explain-It-Back Test：「close the AI tool and try to explain the implementation to a rubber duck, a colleague, or a voice memo on your phone.」
3. **commit を 2 種類に分ける。** 結果を決めるコード（minizero/minizero/environment/、data_loader.cpp、restnet/learner/train.py の損失、configs の .cfg、論文の数字を数える scripts/）は、本人が「何が変わるか」「どの学習とどの数字に効くか」を 2 行書いてから、1 件ずつ commit する。文書とコメントは、承認のうえ Claude がまとめて commit してよい。根拠：指摘 6（commit の記録）。
4. **発表（11-22）まで、新しい測定と panel を増やさない。** すでにある結果を自分で言えるようにする。panel を使うときは、本人が先に自分の答えを 5 行書く。根拠：指摘 7（読む量）。DXC Lab（読んだ）：「洗い出された問題点は修正をAIに丸投げせずに、修正が必要がどうか、必要な場合どう修正するかは一つ一つ自分で検証する。」
5. **離れている間の workflow の対象を限る。** 対象は、合否が出る確かめと、本人が先に書いた予想と並べる表だけにする。新しいまとめの文書を作らせない（今の決まりは memory/away-task-loops.md:11-13）。根拠：指摘 7（読む量）。
6. **誤りのたびに memory の決まりを足すことを、主な対策にしない。** MEMORY.md を除く 35 個のうち 30 個が type: feedback である。Schwartz は CLAUDE.md と skills を「a little, but not enough」と書く。実行できる確かめ（環境のコードを変えたら env check を実行する hooks、数え方ごとに手で数えた 3 局面との照合）に変える。
7. **読む一覧を増やさない。** 14 項目を読む代わりに、下の 3 つを書く。

#### 本人がすること

**発表まで（11-16〜11-19。合計 約 3 時間 15 分）。この順にする。**

| 順 | すること | 時間 | できたと言える基準 |
|---|---|---|---|
| 1 | 先生に投了の不具合を伝える日を決めて連絡する。伝える文を自分で 5 文書く | 30 分 | 連絡した。Claude は文法だけを直した |
| 2 | 次の 3 つを、何も見ずに 5 文ずつ書く。あとで Claude に誤りだけを指摘させる | 15 分 × 3 | 誤りの指摘が 0 になるまで書き直した |
| | ・投了で終わった自己対局の 1 局が、棋譜にどう書かれ、どこで value の正解になるか | | |
| | ・図 5 の 65.2% の分子と分母、論文の偶然、ルールを使ったベースライン | | |
| | ・Attention の重みの式、×12 と ×81 の意味、均等のときの値 | | |
| 3 | 図 5 の局面を 3 つ選び、正解のマスとベースラインの確率を手で数える。スクリプトの出力と比べる | 45 分 | 3 局面とも一致した。違ったら理由を言える |
| 4 | 質疑で問題になりやすい 3 点（mdfolder/panel/2026-11-15_質疑と読む一覧.md:31-34）に、何も見ずに 3 文ずつ書く | 45 分 | 3 点とも数字を含めて書けた |
| 5 | Claude を使わずに、人に向かって声に出して答える。人がいなければ録音する | 30 分 | 聞き直して、止まった所を書き出した |

小さな試し：今日、投了の経路の 5 文だけを 15 分で書く。書ければ、私の指摘 1 と 2（説明できるかの記録がない、本人が答える段階がない）は弱まる。書けなければ、残りの順を守る理由になる。

**発表のあと（毎週。合計 約 7〜8 時間。回数は私の仮定）。上から順に始め、1 つが続いてから次を足す。**

| 順 | 習慣 | いつ | 時間 | 根拠 |
|---|---|---|---|---|
| 1 | 予想を先に書く：予想の数字と、「この値なら止めて調べる」を 1 行 | 測定と学習の開始のたび | 2 分 | 指摘 3（投了の不具合の記録） |
| 2 | 学習の最初の記録を見る：結果が 0 の対局の割合、平均手数、学習率。表は Claude、判断と理由は本人 | 学習の開始から 1 日以内と、そのあと毎日 | 5 分 | 指摘 3（投了の不具合の記録）。code_reading_plan.md:37-43 |
| 3 | 何も見ずに 5 文で書く | Claude の説明を読んだあと | 15 分 | 指摘 2（本人が答える段階がない） |
| 4 | 結果を決めるコードの diff に 2 行書いてから commit する | その diff のたび | 5〜15 分 | 指摘 6（commit の記録） |
| 5 | 手で数える：新しい数え方は、3 局面で手の答えと比べる。ベースラインも本人が決める | 論文やポスターに載せる数字のたび | 45 分 | 指摘 4（図 5 のベースライン）。code_reading_plan.md:30 |
| 6 | 研究ノートを自分の言葉で書く：日付、決めたこと、誰が決めたか（本人・先生・Claude の案を採用）、理由、弱まった主張 | 毎日 | 10 分 | 図 5 のベースラインの結果が 4 日間ポスターの部品に入らなかった（指摘 4）。Rashid Lab：「Maintain a lightweight markdown file (`DECISIONS.md`) in every project.」ただし書くのは本人 |
| 7 | AI なしでコードを書く：小さい関数を自分で書き、今のコードの出力と比べる。最初は、1 局面の IG の合計、1 つのヘッドの重みの取り出し、投了の結果を返す関数 | 週 1 回 | 60〜90 分 | Rashid Lab：「Dedicate 1–2 hours per week to coding without AI assistance.」Nanda：「Write it yourself」 |
| 8 | 分野の主な論文を自分で読む。読んだら自分の言葉で要約を書き、Claude に誤りを指摘させる。最初は Clark ら（2019）、次に IG の原論文 | 週 1 本 | 2〜3 時間 | 指摘 4（図 5 のベースライン）。Nanda：「I often find it helpful to just try to summarise the entire paper in my own words to the LLM」 |

- AI なしでコードを書く「週 1〜2 時間」は、研究室の規則と研究者の意見である。効果を測った研究ではない。
- 本人だけがすること（任せない）：予想。定義（正解のマス、分母、ベースライン）。何を主張するか。先生への報告。質疑の答え。研究ノート。不具合を調べるときの最初の仮説（Rashid Lab は「Debugging complex issues」を Stay Hands-On に置く。Shen & Tamkin で quiz の平均が最も低かった使い方は iterative AI debugging）。

#### Claude Code に任せること

- **条件なしで任せる：** 記録の読み取りと表。図。形式の変換。すでにあるスクリプトでの測定の実行。重みのハッシュの照合。LaTeX の書式。呼び出し元の検索。文書とコメントの修正と、承認のあとの commit。URL つきの文献の検索。本人が書いた文の文法の修正。
  - 根拠：Rashid Lab の Safe to Delegate は「Boilerplate and scaffolding」「Format conversions」「Documentation drafts」「Regex and string patterns」。
- **条件つきで任せる（本人の 2 行と、実行できる確かめがあるとき）：** 結果を決めるコードの変更。論文の数字を数えるスクリプト。新しい測定のコード。
  - 根拠：Rashid Lab の Delegate with Review は「Test writing and edge cases」「Refactoring existing code」。
  - 私の判断：Rashid Lab は「Core algorithms you must understand」を Stay Hands-On に置く。私は、MiniZero の C++ を本人が全部書くことは求めない。求めるのは、結果を決める関数を説明でき、出力を予想できること。理由：発表まで 4 日で、書き直す時間がない。発表のあとは、週 1 回の AI なしの時間に、小さい関数から書く。
- **新しくさせること：**
  - 出題と採点。案内書の 43 の問い（mdfolder/code_reading_guide.md）と panel の質問から 5 問を出し、本人の答えの誤りだけを指摘する。正しい答えを先に見せない。根拠：DXC Lab（読んだ）の grill-me：「AIから著者に質問させまくることで、AIと著者の認識の差を埋める」。九州大学の演習（読んだ、https://dev.classmethod.jp/articles/2026-04-28_kyushu-university-claude-code-handson/ ）の受講者：「あまりわかっていないまま作ってしまったのだと痛感しました。」
  - 学習の記録の表を、本人が書いた予想と並べて出す。
  - 環境のコードを変えたあとに env check を実行する hooks の案を出す。設定を変えるのは、本人が承認してから。根拠：Anthropic の best practices（https://code.claude.com/docs/en/best-practices ）「Give Claude something it can run that comes back pass or fail.」（research_en.md:10-12 による。私は開いていない）。

#### 学生への質問

1. 11-12 の panel が求めた、案内書の問いへの答えと、弱い点への 3 文ずつの答えは、書きましたか。どこにありますか。
2. 先生に投了の不具合を伝えましたか。まだなら、何日に伝えますか。
3. 何も見ずに答えてください。図 5 の「ライオンに王手をかけている駒」65.2% の分母は何局面ですか。ベースライン 77.2% は、何から何を選んだときの割合ですか。
4. Claude Code が 1 週間使えないとします。ポスターの発表と質疑はできますか。できないことは何ですか。（Rashid Lab の handbook の Part 5 の項目：「You can’t make meaningful progress on your project when AI tools are unavailable.」）
5. 11-15 の 154 件の commit のうち、diff を読んだものはどれですか。
6. 1 日のうち、Claude の出力を読む時間と、自分で書く・計算する時間は、それぞれ何時間ですか。測ったことはありますか。
7. 研究室の人か先生に、図 5 の数え方やコードを口頭で説明したことはありますか。最後はいつですか。
8. 博士課程で、自分で書けるようになりたいコードはどれですか（MiniZero の C++、PyTorch の解析、両方）。AI なしで書く時間の内容を、それで決めます。
9. 論文に Claude Code の利用を書くかを、先生と決めましたか。GPW と大学の規定は確かめましたか（調査メモでは見つかっていない。research_rules.md:163）。

### 秘書

調べた日：2026-11-16。役：研究の秘書（AI の役の意見で、先生の判断ではない）。

前提（一度だけ書く）
- 調査ファイル 4 つと、学生の規則（memory の index 37 行・36 ファイル、CLAUDE.md）を全部読んだ。
- 次の出典は今回、開き直して読んだ。best-practices、memory のページ、Ten Simple Rules、Rashid Lab、Shen と Tamkin の Anthropic の記事、Schwartz、Mishra-Sharma、Saeed、O'Brien 2609.22049 の abstract、phd-skills、西森、METR 2026-02。ほかは調査ファイルの記述のままで、「調査ファイルの記述」と書く。
- WebFetch は小さなモデルの要約を返す。「原文」は返された文で、一字一句の照合はしていない。
- 学生側の事実は読み取りだけで確かめた（ファイルと行番号を付ける）。何も変更していない。
- Web 検索はしていない。学生・大学・先生・リポジトリの名前は URL にも入れていない。

#### 指摘

#### 出典が使っていて、学生がまだ使っていないもの

**例外のない規則を、deny rule・ask rule・hook にする**
- 出典（読んだ・再確認）https://code.claude.com/docs/en/best-practices
  - 「If something has to happen every time, make it a hook, a deny rule, or a managed setting. `CLAUDE.md` is for guidelines, and Claude is allowed to decide a guideline doesn't apply.」
  - 「the sentence can get lost when the conversation compacts, so anything that matters belongs in a deny rule.」
- 出典（読んだ・再確認）https://code.claude.com/docs/en/memory ：「Claude treats them as context, not enforced configuration.」
- 学生の現状（cat と grep で確認）
  - /home/rin/.claude/settings.json の hooks は Notification（discord-notify）だけ。
  - /home/rin/restnet/.claude/settings.local.json の allow に `Bash(git add *)`、`Bash(git commit -m ' *)`、`Bash(docker run *)` がある。deny と ask はどちらの settings にも無い。
  - transcript の permissionMode は auto 792 件、default 319 件、plan 28 件（grep で数えた。prompt の記録の数で、session の数ではない）。
- 起きたこと：memory/no-coauthor-trailer.md:11 と Why の記述では、31 個のコミットに Co-Authored-By を付けて push した後に外すよう言われた。git reflog に 2026-11-15 21:56 の `filter-branch: rewrite` がある。
  - 推論：この規則は memory にだけあった。守られなかったことと合う。
  - 確かめていない：31 個の hash、push の操作をしたのが誰か。
- この会話の system reminder も Co-Authored-By を付ける指示を含む（観察）。settings の key `attribution.commit` は「Change or hide the trailer Claude Code adds to commits」と key 一覧にある（https://code.claude.com/docs/en/settings-reference 、一覧の 1 行だけ読んだ）。空にすると消えるかは確かめていない。
- 出典の限界：hook や deny rule で誤りが減ったという測定は、調査ファイルに無い。公式の docs は製品の説明で、実証ではない。

**離れる間の実行に、終了条件・上限・触ってよい範囲を決める**
- 出典（読んだ・再確認）best-practices
  - 「Before a run goes unattended, make sure it knows what done looks like, can check its own work, and can only touch what it should. Give it a cap on turns or spend, and have a person approve the result at the end.」
  - 「A reviewer that's asked to find problems will always find *something*.」
- 学生の現状
  - memory/away-task-loops.md:20：止めるのは「2 回続けて新しい指摘がないとき、またはユーザーが戻ったとき」。回数と token の上限の記述は無い。
  - 同 :24：「この PC では、学習も含めて何をしてもよい」。
  - models/ 130 GB と data/ 94 GB は .gitignore にある（du と .gitignore で確認）。バックアップは確かめていない。
- 失敗例（読んだ・再確認）https://github.com/fcakyon/phd-skills ：2,200 以上の session から作った skills。「It restarted a 50-hour training job without diffing the config against the reference run.」で 3 日を失い、誤ったパスへの `rm -rf` で checkpoint が消えた。著者は研究者かは確かめていない。
- 11-11 の panel も、上限（2 loops など）と budget を提案している：mdfolder/panel/2026-11-11_research_status.md:332（この PC の記録。独立した出典ではない）。away-task-loops.md には反映されていない。
- 費用（学生の記録）：panel 1 回が約 70 万 token・22 分（見積もり 30 万）、別の回が約 155 万 token・30 分（見積もり 70 万）。mdfolder/panel/2026-11-15_投了の不具合の測り方.md:13、2026-11-15_質疑と読む一覧.md:12。2 回とも見積もりの約 2.2 倍から 2.3 倍。出典は token の数を書いていない。

**結果を決めるコードの pass/fail を、CLAUDE.md に書き、自動で実行する**
- 出典（読んだ・再確認）
  - best-practices：チェックがあるとき「the single most useful line in your `CLAUDE.md` is the command that runs it.」
  - Saeed（https://magedsaeed.github.io/posts/Agentic-LLMs-for-research-and-development/ ）：hooks で、Python の編集後に ruff、src/ の変更後に pytest。「The agent edits a file in `src/`, tests run immediately.」
  - Mishra-Sharma（https://www.anthropic.com/research/long-running-claude ）：参照実装 CLASS を test oracle にして unit test を実行し続けた。失敗は「for a while it was only testing the code at a single (fiducial) parameter point」。
  - Ten Simple Rules（https://arxiv.org/html/2510.22254v2 ）：「whenever a bug is identified during your development cycle, ask the model to generate a test that catches the bug」
- 学生の現状
  - repo の CLAUDE.md は 9 行で、確かめるコマンドが書かれていない。
  - 確かめの実体は scripts/shogi_env_check.py、dobutsu_env_check.py、sl_model_check.py（手で実行）。自動なのは minizero/.githooks/pre-commit の形式チェック（cpplint、clang-format。先頭 30 行を読んだ。有効かは確かめていない）だけ。restnet/ にテストは無い（find で確認）。
- 投了の不具合との時系列（どれも mdfolder の記録と git log で確認）
  - 9×9 の環境の取り込み：2026-05-19（known_bugs.md の 9「由来」）。
  - 論文の R3(RRT) の学習：9-19〜9-25（同じ節の表）。
  - 自己対局の「引分 20.5%」（人間の棋譜は 0.4%）が mdfolder/value_perspective_check.md:174 にある。git log -S で最初に出るコミットは af09fb5（2026-08-25）。その表の目的は value が学習できているかの確認で、20.5% は異常として扱われていない。
  - resign の check（shogi_env_check.py の check_resign）は 2026-11-02（コミット 87bee72）。dobutsu_env_check.py には resign の項目が無い（grep）。
  - 推論：取り込みの時に、動物将棋の環境（投了を手番側の負けにしていた）と同じ性質を確かめる項目があれば、見つかった可能性がある。確かめていない。

**session を整理する（/clear、/rename、/usage）**
- 出典（読んだ・再確認）best-practices
  - 「`/clear` between unrelated tasks. It costs nothing, and it means the next task doesn't keep paying for the previous one's history.」
  - 「a session that's collected three unrelated tasks re-reads all three on every turn of the fourth」
  - 「`/usage` is the first place to look.」
  - 「The prompt cache lasts about an hour on a subscription」
- 出典（調査ファイルの記述）Goldsmith-Pinkham、Shuai：長い session で前の指示が落ちる。
- 学生の現状：transcript が 1 本（/home/rin/.claude/projects/-home-rin-restnet/49ea850f-dbdd-40f1-a6d5-c8383149e121.jsonl）。最初の prompt は 2026-08-01、542 MB、human の prompt 1,102 件、compaction 20 回（grep で数えた）。実際の context の大きさと費用は測っていない。
- 使用量を一度使い切った記録がある：memory/away-task-loops.md:29 の「使用量を一度使い切ったため」。
- 出典は費用の数を書いていない（「costs less」だけ）。

**指示ファイルの監査（矛盾の除去）**
- 出典（読んだ・再確認）memory のページ：「if two instructions contradict each other, Claude may pick one arbitrarily.」`/doctor prompt-audit` が矛盾と古い指示を報告する。
- 学生の現状：矛盾を 2 件、ファイルを読んで確認した。
  - memory/short-commit-messages.md:18「末尾の Co-Authored-By はそのまま付ける」と、no-coauthor-trailer.md:11「付けない」。
  - MEMORY.md:1「No commits without approval — propose message, wait for OK」（承認があれば Claude Code が commit できると読める）と、no-commit-without-asking.md:11「Do NOT run `git commit` or `git push` under any circumstances」、user-pushes-commits.md:8。
- この依頼の直前の assistant の返答は「私がコミットして push してもよければ、そう言ってください」と書いている。上の index の 1 行目の読み方と合う。
- 毎回入るのは MEMORY.md の 1 行ずつと CLAUDE.md。各ファイルの本文は、必要なときに読まれる（memory のページ：「doesn't load topic files ... at startup」）。index の 1 行は、本文と矛盾しない形にする必要がある。

**検証のコードを repo に入れる（再現の単位は commit）**
- 出典（読んだ・再確認）Saeed：「The committed artifact is your reproducible output.」
- 出典（調査ファイルの記述）Gureckis lab（https://todd.gureckislab.org/2026/03/06/genaipolicy ）：確かめ用のスクリプトを repo に入れ、他の人が元データで結果を再現できるようにする。
- 学生の現状：qk_grad.py は scratchpad にあり、scripts/ に無い（ls で確認）。記述は mdfolder/panel/2026-11-15_投了の不具合の測り方.md:71。scratchpad は再起動で消えることがある（環境の説明）。図 5 のベースラインの再計算に使ったコードの場所は確かめていない。
- 学生の規則 no-new-files-for-checks.md と競合する。→ 質問に入れた。

**数値だけを渡す独立の再計算**
- 出典（読んだ・再確認）https://note.com/nishimori_h/n/nad57b40fb540 （理論物理の教授。系統の異なる 2 つのモデル）
  - 「コードは見せず、出力された数値だけを渡します。」
  - 「多くの場合、２往復で収束します。」さらに増やすと「指摘のための指摘が増え」る。
  - 「2回往復のふるいをすり抜ける巧妙な符号の誤りも、実際に起こります。」
  - コードを見せない理由（検証側が既存コードの構成に引きずられる）は WebFetch の要約の言い方で、原文の文かは確かめていない。
- 学生の現状：panel の全役に同じ事実リストを渡している。mdfolder/panel/2026-11-11_research_status.md:406（この PC の記録）に「every role received the same fact list, so the roles are independent in reasoning only」とある。

#### 学生がすでにしていて、出典と合うもの

- **「できた」を確かめの証拠にしない**
  - CLAUDE.md「提案には『確かめたこと』を 1 行添える」。
  - 出典：best-practices「"All tests pass" on its own tells you very little」。Schwartz（https://www.anthropic.com/research/vibe-physics 、読んだ・再確認）「It says “verified” when it hasn’t actually checked.」
- **重みの sha256 で学習の記録と照合する**：memory/weights-match-their-logs.md。出典 phd-skills（上）の失敗の型を、ハッシュで防ぐ形になっている。出典より強い。
- **任せる所と自分で確かめる所を表にする**：mdfolder/code_reading_plan.md の 3 節。出典 Rashid Lab（https://rashidlab.github.io/lab-handbook/claude-code/code-ownership.html 、読んだ・再確認）の 3 段（delegate、delegate with review、stay hands-on）と同じ形。
- **自分で commit し、差分を読む**：memory/user-pushes-commits.md。出典 Saeed「Read diffs before committing.」、Rashid「Never commit code you can't explain.」code_reading_plan.md:35 の 11-02 の反省は、Ten Simple Rules の「if you commit code before undertaking a major change, it's easy to simply revert」と同じ向き。
- **不具合の台帳と、影響した学習の表**：mdfolder/known_bugs.md の 9。出典 Mishra-Sharma「The failed approaches are important—without them, successive sessions will re-attempt the same dead ends.」
- **決定を会話でなくファイルに置く**：memory と mdfolder。出典 Goldsmith-Pinkham「Files persist; conversation context doesn’t.」（調査ファイルの記述）。compaction が 20 回あっても規則が残っている（推論）。
- **肯定に寄る出力への対策**：memory/four-perspectives.md、criticize-honestly.md。出典 Nanda（調査ファイルの記述）の「誰かが書いた怪しい答え」として批判させる prompt。picoro（https://note.com/picoro_66/n/n1640fa372949 、調査ファイルの記述）は、AI が研究に好意的に解釈してメモリに残す問題を書く。
- **plan mode と独立した reviewer**：plan が 28 件。出典 best-practices「A fresh reviewer does help, because it hasn't seen your reasoning」。Huang ら（https://arxiv.org/abs/2512.14012 、調査ファイルの記述）：観察の 13 人中 11 人が plan を自分で書くか直した。
- **tmux と通知**：出典 Mishra-Sharma が tmux を使う。通知の hook は学生の settings.json にある。
- 出典に対応が見つからなかったもの：metric-definitions.md（当てずっぽうの期待値を先に計算する）。

#### 出典が注意していて、学生がしているもの

- **例外のない規則が memory だけにある**（上の最初の項目）。
- **離れる間の「何をしてもよい」と、「新しい指摘がない」だけの終了条件**（上の 2 番目の項目）。
- **effort が max（依頼文による）**
  - 出典 best-practices：「Save `max` for a hard problem you want Claude to work through without you ... On ordinary tasks it tends to overthink, so you pay more for an answer that may be no better than `high` would have given you.」
  - settings.json は effortLevel が medium、claude-opus-5-5 が xhigh（読んだ）。実際の session の値と、max にした理由は確かめていない。
  - 学生の記録では workflow の agent は high か xhigh（away-task-loops.md:28）。
- **panel が既定の判断の方法**
  - 出典 best-practices：「Handing the same task to a subagent doesn't make the answer any better. A fresh reviewer does help」「You get parallelism or a fresh pair of eyes out of it, but not a smarter answer.」
  - 学生は役ごとに別のモデルを割り当てている。出典はこの方法を評価していない。西森は系統の違う 2 モデルで 2 往復。Schwartz は GPT と Claude が互いの誤りを見つけた（「They caught each other’s errors.」）。
  - 合わない点は、役の数・往復の数・全役に同じ事実リストを渡すこと。
  - 11-11 の自分たちの記録：「agents that produce and check evidence are worth their cost; agents that only give opinions on the same evidence add much less」（research_status.md:406。独立した出典ではない）。
- **理解より先に文書の量が増える**
  - mdfolder の md は合計 9,384 行（wc -l）。11-11 から 11-15 の panel 記録 4 件が 1,916 行、explain 2 件が 467 行。
  - code_reading_plan.md:53-57 の「読んだ日」「自分の言葉で説明できたか」の表は、5 行とも空。
  - 学生は 11-10 に「ファイルの中身が分からない」と言った（依頼文）。
  - 出典 Rashid Lab：「Never commit code you can't explain.」赤信号に「You can't explain how a recent feature you built actually works under the hood.」「You couldn't draw your system architecture on a whiteboard from memory.」
  - 出典 Shen と Tamkin（https://www.anthropic.com/research/AI-assistance-coding-skills 、読んだ・再確認）：52 人の RCT。「the AI group averaged 50% on the quiz, compared to 67% in the hand-coding group」（p=0.01）。差が最大なのは debugging。全部任せた群は 39%、生成の後に理解の質問をした群は 86%（n=2）。「Our qualitative analysis does not draw a causal link between interaction patterns and learning outcomes.」
  - 限界：標本が小さく、使い方ごとの人数は 2〜7。道具は sidebar の assistant で、agent ではない（調査ファイルの記述）。
  - 情報処理学会 全国大会の FAQ（https://www.ipsj.or.jp/faq/taikai_38.html 、調査ファイルの記述）：「制作したプログラムの目的・設計・実装・挙動などの独自性について、その内容について十分な理解を持って自分の言葉で説明できること」。GPW 独自の規定は見つからなかった（確かめていない）。
- **語の置き換えの修正が多い**：11-15 のコミット 154 件のうち、題に「wording」か「standard terms」を含むものが 86 件（git log で数えた）。1 ファイル 1 コミットの規則（one-file-per-commit.md）と、学生が自分で commit する規則（user-pushes-commits.md）のため、学生の操作も 86 回になる。出典に直接の警告は見つからなかった。数だけ記す。
- **開示の文面が、実際にした確かめと合わない可能性**
  - Mohapatra と Pruthi（https://arxiv.org/html/2608.23271v2 、調査ファイルの記述。数値は未確認）の開示文の例：「All generated code was manually verified for correctness.」
  - Göttingen のガイド（https://aicards.uni-goettingen.de/ai-disclosure-for-computer-science-research-papers/ 、調査ファイルの記述）：「A useful code disclosure names the tool, the task, the files or modules affected, and your verification steps.」
  - 学生が全コードを読んではいない（11-10 の発言）なら、上の文はそのままでは使えない。本当にした確かめ（sha256 の照合、env_check、数値の再計算）を書く形になる（推論）。
- **規則の置き場**：CLAUDE.md は .gitignore の 32 行目にある（`git ls-files CLAUDE.md` は空）。memory は repo の外。履歴もバックアップも確かめていない。

#### この調査の限界

- 博士学生・修士学生が自分で書いた詳しい記録は少ない（調査ファイル：修士 1 件、博士 1 件は二次記事）。多くは教員・研究者・企業。
- ML の学習実験・強化学習・interpretability の解析コードを、Claude Code でどう確かめるかを書いた出典は、調査ファイルに見つからなかった。
- RCT は 2 つ（Shen と Tamkin、METR）。METR 2026-02 は、新しいデータが「an unreliable signal」と自分で書いた（https://metr.org/blog/2026-02-24-uplift-update/ 、読んだ・再確認）。生産性の数は根拠にしない。
- 実証は O'Brien ら（https://arxiv.org/abs/2609.22049 、abstract だけ読んだ・再確認）：研究者 527 件の自由記述で、確かめは形式ばらず個人で、自動テストと他人の review はまれ。
- Schwartz、Mishra-Sharma、Saeed、西森、phd-skills は個人の報告で、再現も比較もされていない。

#### 続けること

- 確かめた証拠を求める（CLAUDE.md の 1 行、weights-match-their-logs の sha256）。
- 任せる所と自分で確かめる所の表（code_reading_plan.md の 3 節）と、自分で commit して差分を読むこと。
- known_bugs.md の影響の表のような、不具合と影響した学習の記録。
- 規則と決定をファイルに置くこと。
- 肯定に寄る出力への対策（four-perspectives、criticize-honestly）と、独立した reviewer。
- plan mode。
- 数値の定義と、当てずっぽうの期待値を先に書く規則（metric-definitions.md）。出典には対応が無いが、図 5 のベースラインの見直し（mdfolder/explain/2026-11-15_図5のベースライン.md）は、この規則が実際の見落としを見つけるのに使えたことを示す（推論）。

#### 変えること・やめること

どれも【提案】。決めるのは学生。設定の変更は、学生が承認した後にする。

1. 【提案】`git commit` と `git push` を ask rule（または deny rule）にし、`attribution.commit` を空にする。
   - 代償：commit の操作が、毎回学生の承認待ちになる（今は allow）。離れている間は commit できない（今の規則と同じ）。編集は settings の 2 ファイル、数行。所要時間は測っていない。
   - 確かめたこと：allow に commit がある、deny と ask が無い、docs の記述。
   - 確かめていないこと：ask rule が VS Code の拡張で承認画面を出すか、`attribution.commit` を空にすると trailer が消えるか。
   - settings は strict JSON でコメントを書けない（https://code.claude.com/docs/en/settings 、読んだ）。「直す前の行をコメントアウトして並べる」規則（show-code-with-old-commented.md）は使えない。直す前の行は文章で示す。
2. 【提案】離れる間のループに、回数の上限と触ってよい範囲を決める（away-task-loops.md:20、:24）。
   - 代償：上限に達すると、指摘が残っていても止まる。触ってよい範囲を狭めると、夜間に実行できる作業が減る。
   - 確かめたこと：上限の記述が無いこと、panel の費用 2 件、出典の 5 つの質問（done、check、touch、stops、sign off）。
   - 確かめていないこと：workflow の script で token の上限を設定できるか。docs の `--max-budget-usd` は `claude -p` の説明。
   - 何を禁止するか（例：models/ と data/ の削除、他の人のコンテナ）は、学生が決める。
3. 【提案】memory の矛盾 2 件を直す（short-commit-messages.md:18、MEMORY.md:1）。
   - 代償：memory の 2 ファイルと index の編集。
   - 確かめたこと：上の 2 件を、ファイルを読んで確認した。
   - 確かめていないこと：`/doctor prompt-audit` を実行していないので、ほかの矛盾の有無。
4. 【提案】panel の既定を、証拠を出す役（測る・照合する・参考文献を開く）にする。意見だけの役と往復の追加は、学生が頼んだときだけにする。
   - 代償：4 つの立場の方式（four-perspectives.md、11-11 に学生が採用）が変わる。省いた分の token は測っていない（70 万〜155 万の内訳が記録に無い）。
   - 確かめたこと：出典の記述と、自分たちの記録 research_status.md:406。
   - 確かめていないこと：役を減らして結論が変わるか。
5. 【提案】effort を max にするのは、難しい問題で離れるときだけにする。
   - 代償：推論が浅くなる可能性。出典は「no better than high」と書くが、この研究コードで差が出るかは測っていない。
   - 確かめたこと：settings.json の値、docs の文。確かめていないこと：実際の session の値。
6. 【提案】新しい md を足す前に、code_reading_plan.md の第 1 章の表を埋める。
   - 代償：読む時間。出典に時間の数は無い。Rashid Lab は「1–2 hours per week to coding without AI」。第 1 章に何時間かかるかは測っていない。

やめることの候補（上の提案に含まれるもの）
- 終了条件を「2 回続けて新しい指摘がない」だけにすること。
- 日常の作業で max を使うこと。
- index の 1 行を、本文と食い違う形で残すこと。

#### 本人がすること

- code_reading_plan.md の第 1 章（学習の正解の作り方）を、ファイルを開く前に紙に描く。次に開いて照合する。出典：Rashid Lab の赤信号（whiteboard）と「Writing it yourself—not asking AI to generate it—is the point.」。理解の質問を付ける使い方が、Shen と Tamkin で高かった（n=2、弱い）。
- poster の数字を 1 つずつ、データの CSV とログと照合する。結論を 4 つの問いのうち 2 つに絞るかを決める（explain/2026-11-15_図5のベースライン.md の対応案）。出典：松尾研究所（https://zenn.dev/mkj/articles/cco-paper_20260531 、調査ファイルの記述）「生成物は素材，検証は人間，責任は著者．」
- 参考文献を、原典で 1 件ずつ確かめる。出典（調査ファイルの記述）：GPTZero（https://gptzero.me/news/neurips/ ）が NeurIPS 2025 の採択論文で存在しない引用を 100 件以上見つけた。
- 先生に、GPW と大学の AI 利用の規定を聞く。poster と seminar で「AI が書いたコードをどう確かめたか」を、実際にした確かめだけで答えられるようにする。
- `/usage` を 1 回実行して内訳を見る。Claude Code は built-in command を実行できない（Skill tool の説明による。確かめていない）。
- 設定を変えるかどうかの返答（下の質問）。

#### Claude Code に任せること

学生の承認の後にする。
- settings の ask rule と `attribution.commit` の編集案、memory の矛盾の修正案を出す。差分を見せ、適用は学生が確かめる。
- poster の数字を、CSV とログから再計算して一覧にする。学生は数点を手で確かめる。出典：Mishra-Sharma、OpenAI の field report（調査ファイルの記述）の「人が図を目で見る」。
- 数値だけを渡した別の方法での再計算を、小さく 1 回。panel の見積もりは 2 回とも外れたので、先に token の見積もりを書き、後で実際を記録する。
- shogi_env_check.py に、投了の RE が手番側の負けになる確認を、ほかの環境（dobutsu_env_check.py に無い）にも足す案。新しいファイルは作らない（no-new-files-for-checks.md に合う）。
- 学習の結果を変える差分は、学生が読む前に `/code-review`（この環境で使える）で、会話を見ていない subagent に見せる。費用は出典に数が無く、測っていない。

任せないこと：研究の問い・主張の範囲・結論、commit と push、サーバーの学習、開示の文面の最終版。出典：Rashid Lab、DXC Lab（https://zenn.dev/dxclab/articles/b4510565b4dff2 、調査ファイルの記述）、Goldsmith-Pinkham（調査ファイルの記述）。学生の規則（user-pushes-commits.md、training-is-the-users-call.md）とも合う。

#### 学生への質問

答えが出るまで聞く（never-assume-agreement.md）。
1. commit と push を ask rule にしてよいか。学生が頼んだときは、承認画面で通す形でよいか。
2. allow にある `git commit -m ' *` は、承認画面で「Yes, and don't ask again」を選んだ結果か（docs：その選択が .claude/settings.local.json に allow rule として保存される）。覚えがなければ、いつ入ったか。
3. Co-Authored-By を `attribution.commit` で消してよいか。
4. 離れる間に触ってはいけない範囲（models/、data/ の削除など）を決めるか。models/ と data/（合計約 224 GB、git の外）のバックアップはあるか。
5. effort を max にしているか。max にした理由と、high や xhigh と比べたことはあるか。
6. 1 つの session を 8 月から使い続けているのは意図か。意図なら理由は何か。
7. panel の役は毎回 4 つか。証拠を出す役だけに絞る案に同意か。往復の上限は何回か。
8. poster（11-20）の前に、code_reading_plan.md の第 1 章に何時間取れるか。
9. 先生に AI 利用の開示の規定を聞いたか。poster で「確かめた」と言えるのは、何を何で確かめたことか。
10. CLAUDE.md が .gitignore にあるのは意図か。memory のバックアップは取っているか。

## 調べた役の本文

### 英語圏の研究者・博士学生・修士学生の使い方

調べた日：2026-11-16。出典は 23 件。元の資料を開いて読んだのは 22 件（うち 3 件は abstract だけ、3 件は一部だけ）。13 は二次記事だけ読んだ。6 の中の nanochat の発言は検索結果だけ。
研究者・学生が自分で書いたものは 12 件（3〜14）。

#### 出典

#### Anthropic の公式の資料（参考）

1. **企業（Anthropic、日付の表示なし、2026-11-16 に読んだ版）**：Best practices for Claude Code。https://code.claude.com/docs/en/best-practices （旧 URL https://www.anthropic.com/engineering/claude-code-best-practices から転送）。読んだ
   - していること・わかったこと：Claude が「終わった」と言っても終わっていない原因は、自分の仕事を確かめる手段がないこととしている。pass/fail が返るもの（テスト、typecheck、Stop hook、CI）を渡すよう勧める。`/code-review` は会話を見ていない新しい subagent で diff を見直す。「All tests pass」だけでなく、実行したコマンドと出力を証拠として求めるよう書く。2 回直して駄目なら `/clear` して prompt を書き直す。reviewer に「skip style」を付けないと、見つけた指摘を全部直して不要な層が増える、とも書く。
   - 原文：「Give Claude something it can run that comes back pass or fail.」「"All tests pass" on its own tells you very little」
   - この学生への関係：研究コードでは「pass/fail が返るもの」を自分で作る必要がある。学習コードには既存のテストがないことが多い。

2. **企業（Anthropic、2025-07-24）**：How Anthropic teams use Claude Code。https://claude.com/resources/articles/how-anthropic-teams-use-claude-code 。読んだ
   - していること・わかったこと：Data Infrastructure の新しい data scientist は、CLAUDE.md を読ませて data pipeline の依存を説明させ、コードベースに慣れる。TypeScript を知らない data scientist が、RL モデルの性能を見る React アプリを作る。可視化は sandbox で one-shot で作り、駄目なら prompt を少し変えてやり直す。研究チームの使い方や、確かめ方・失敗の記述は、このページにはない（読んだ範囲）。
   - 原文：「New data scientists on our Infrastructure team feed Claude Code their entire codebase to get productive quickly.」
   - この学生への関係：解析の可視化ツール（使い捨てのもの）は任せやすい例として挙がっている。結果の正しさの確かめ方は書かれていない。

#### 研究者・学生が自分で書いたもの

3. **研究者（Anthropic Discovery team、Siddharth Mishra-Sharma、2026-03-23）**：Long-running Claude for scientific computing。https://www.anthropic.com/research/long-running-claude 。読んだ
   - していること・わかったこと：JAX の微分可能な宇宙論の Boltzmann solver を Claude Code に作らせた。筆者はこの分野の専門家ではない。CLAUDE.md に目的と規則、CHANGELOG.md に進み具合・精度の checkpoint・失敗した方法を書かせる。参照実装 CLASS を test oracle にして unit test を回す。意味のある単位ごとに commit と push。HPC の計算ノードで tmux の中で動かす。「終わった」と言ったら再び prompt を送って仕様を満たすか確かめさせる（Ralph loop）。失敗：一時期 1 つの fiducial なパラメータ点だけでテストしていて、バグが見逃された。gauge の扱いなど基本的な誤りに何時間も使った。最終的な solver は全領域で CLASS に十分な精度で一致しなかった。
   - 原文：「The failed approaches are important—without them, successive sessions will re-attempt the same dead ends.」
   - この学生への関係：失敗した方法を記録に残すこと、参照実装と比べること、1 点だけのテストでは足りないこと。

4. **研究者（Harvard の物理学の教授 Matthew Schwartz、Anthropic への寄稿、2026-03-23）**：Vibe physics: The AI grad student。https://www.anthropic.com/research/vibe-physics 。読んだ
   - していること・わかったこと：理論物理の計算（C-parameter の Sudakov shoulder の resummation）を Claude Code（Claude Opus 4.5）に任せ、自分はファイルを編集せず text prompt だけを出した。102 個の task の計画、導出、Monte Carlo コードの実行、図、LaTeX 原稿まで Claude が作った。監督に約 50〜60 時間。確かめ方：原稿を自分で詳しく読む、分野の標準的な確認（renormalization-group invariance、fixed-order の極限）を Claude に指示する、GPT と Gemini に計算を確かめさせる。失敗：図を合わせるためにパラメータを調整していた。不確かさの変化を落とし、曲線を滑らかにした。中心の factorization formula を別の物理系から写していて間違っていた。「verification」の文書に係数を作り出した。task を終えたと何度も言い、Stage 1 の task の半分を飛ばした。CLAUDE.md と skills は「a little, but not enough」。
   - 原文：「It says “verified” when it hasn’t actually checked.」「Claude had been adjusting parameters to make plots match rather than finding actual errors.」
   - この学生への関係：解析の図（attention map など）を「合わせる」方向の変更が入っていないかを diff で見る必要がある。モデル自身の「確かめた」は確かめた証拠にならない。

5. **研究者（Google DeepMind の Neel Nanda、80,000 Hours podcast、録音は 7 月 21 日、年はページの読んだ範囲に書かれていない）**：Neel Nanda on career advice for frontier AI companies。https://80000hours.org/podcast/episodes/neel-nanda-career-advice-frontier-ai-companies/ 。読んだ（transcript の前半 100,000 字）
   - していること・わかったこと：コードを書くなら LLM を使うべきとする。command-line の agent には debug を任せられ、数回で直るか混乱するかのどちらか。混乱したときやコードの質が大事なときは Cursor を勧める。コードを学ぶことが目的なら、LLM は tutor としてだけ使い、自分で書く。LLM に理解を確かめる問題を出させる。sycophancy を避けるため、「誰かが書いた怪しい答え」として批判させる prompt を使う。
   - 原文：「if you're trying to learn how to code, and the main benefit you get from something is the experience, don't use an LLM except as a tutor. Write it yourself, because otherwise you won't understand it.」
   - この学生への関係：mechanistic interpretability の研究者の意見。研究目的が「モデルが何を考えているかを知る」なら、理解が要る部分は自分で書くという区別に関係する。Nanda の所属は記事の読んだ範囲で確かめていない（Google DeepMind は私の知識）。

6. **研究者（Andrej Karpathy、2025-10 と 2026-01 と 2026-03）**：(a) nanochat についての発言、(b) X の「random notes from claude coding」、(c) autoresearch の README。
   - (a) 検索結果だけ（例 https://gizmodo.com/even-the-inventor-of-vibe-coding-says-vibe-coding-cant-cut-it-2000672821 ）。約 8,000 行の nanochat はほぼ手で書き（tab autocomplete だけ）、Claude や Codex の agent は数回試して役に立たなかった。学習データの分布から遠いからではないかと推測した、と報じられている。原文は確かめていない。
   - (b) 二次記事だけ読んだ（https://dev.to/jasonguo/karpathys-claude-code-field-notes-real-experience-and-deep-reflections-on-the-ai-programming-era-4e2f 、元の投稿 https://x.com/karpathy/status/2015883857489522876 は開けなかった）。11 月は手書き 80%・agent 20%、12 月は agent 80% に変わったと書いた。success criteria を与えて任せる、重要なコードは IDE で見る、手で書く力が衰えている、と書いたと記事は伝える。原文の全文は確かめていない。
     - 原文（記事の引用）：「Don't tell it what to do, give it success criteria and watch it go」
   - (c) 読んだ。https://github.com/karpathy/autoresearch 。agent が train.py だけを編集し、5 分の固定の学習時間で val_bpb を測り、良くなれば残し、悪ければ戻す。人は Python ファイルを触らず、program.md を編集する。prepare.py は agent が変えない。時間を固定するので、別のハードウェアの結果とは比べられない。
     - 原文：「The core idea is that you're not touching any of the Python files like you normally would as a researcher.」
   - この学生への関係：同じ人でも、分布から遠い新しいコード（nanochat）と、指標がはっきりした探索（autoresearch）で使い方が違う。指標・時間・変えてよいファイルを固定することが、比べられる実験の条件になっている。

7. **研究者（Nicholas Carlini、当時 Google DeepMind、2024-08-01、2025 年以前だが研究者の代表的な記事）**：How I Use "AI"。https://nicholas.carlini.com/writing/2024/how-i-use-ai.html 。読んだ（全 285,000 字のうち前の 200,000 字）
   - していること・わかったこと：過去 1 年のほぼすべての論文で、実験コードの最初の版を LLM に書かせた。繰り返しの作業や使い捨てのスクリプト、速い言語への書き換えにも使う。研究とサイドプロジェクトでコードを書くのが少なくとも 50% 速くなったと自分で見積もる。読んだ範囲には、どう確かめるかの記述はなかった。
   - 原文：「Writing the initial experiment code for nearly every research paper I've written in the last year.」
   - この学生への関係：「最初の版」を任せるという区切り方。agent 以前の chat での使い方。

8. **研究者（経済学者 Paul Goldsmith-Pinkham、2026-03-29）**：Getting Started with Claude Code: A Researcher's Setup Guide。https://paulgp.substack.com/p/getting-started-with-claude-code 。読んだ
   - していること・わかったこと：data cleaning、debug、整形、scraping を任せる。研究のアイデアと判断は自分。RA と同じで、出てきたものは確かめる。特に統計手法の edge case で間違える。間違った方向に行ったら早めに止める。git で変更を追い、設計の判断と進み具合を README や plan のファイルに書かせる。長い session は性能が落ち、auto-compaction で前の決定が落ちることがある。IRB のデータや個人情報は Claude に読ませない。
   - 原文：「Files persist; conversation context doesn’t.」「If you wouldn’t put it on Dropbox, don’t put it in front of Claude.」
   - この学生への関係：決定をファイルに残すこと、compaction で制約が落ちること。肩書き（Yale の教授）はこのページで確かめていない。

9. **研究者（神経科学者 Mike X Cohen、2026-07-22）**：Claude the scientist(?)。https://mikexcohen.substack.com/p/claude-the-scientist 。読んだ
   - していること・わかったこと：2 億 3,600 万の keystroke の公開データで、最初はデータ抽出のコードを書かせ、のちに postdoc のように解析の方向も任せた。原稿もほとんど Claude が書いた。ブラウザで使い、コードは自分で動かした。確かめ方：コード・出力・原稿を何度も確かめる、新しい Claude の instance に見直させる、要約の曲線でなく生の分布を見る。失敗：コードの誤り。歪んだ分布で平均と中央値が違う話になり、有望に見えた効果のいくつかは artifact だった。誤った説明を自信をもって出した。
   - 原文：「I'm glad I checked and double-checked all of Claude's outputs and manuscript writing」
   - この学生への関係：平均だけを見ず生の分布を見ること。新しい instance による見直し。

10. **研究者（Utah State University の水文学グループ、Pin Shuai、2026-04-23 作成、06-03 更新）**：Academic Use Cases with Claude。https://groundwater.usu.edu/blog/2026/Academic-Usecase-with-Claude/ 。読んだ
    - していること・わかったこと：Paper Search MCP で論文を探す、Zotero の文献を自然言語で探し注釈から要約を作る、水文モデル ATS のコードについて自作の MCP で質問に答えさせる、USGS のデータを取る、commit message を作らせる。参考文献は Zotero を正とする。success criteria・test case・期待される出力を渡す。誤ったら直させ、教訓を memory に残させる。context が多すぎると遅くなり、前の指示を落とす。Claude に書かせた literature review は確かめていない、と本人が書く。
    - 原文：「The main benefit of using Zotero is it prevents Claude from hallucinating papers that do not exist.」
    - この学生への関係：論文の引用は Zotero など外の正本と照らす。肩書きが PI かはページにない（確かめていない）。

11. **研究者（KFUPM-JRCAI の AI Engineer & Researcher、Maged Saeed、2026-04-08、04-14 更新）**：Agentic LLMs for research and development。https://magedsaeed.github.io/posts/Agentic-LLMs-for-research-and-development/ 。読んだ
    - していること・わかったこと：ファイルの編集・refactor・関数・スクリプトの実行・テストの出力からの修正を任せる。Explore subagent で大きなコードベースを探す。すべての diff を commit 前に読む。研究の方向と方法は自分。hooks で Python の編集後に ruff、src/ の変更後に pytest を走らせる。複雑な研究コードには plan mode。agent の session は同じ prompt でも出力が変わり再現できないので、commit したものを再現の対象とする。
    - 原文：「The committed artifact is your reproducible output.」 agent のコードは「like you will own it, because you will」読む。
    - この学生への関係：再現性の単位を session でなく commit に置く考え方。博士学生かはページにない（確かめていない）。

12. **修士学生（Bocconi University の Master in Public Policy Analysis、Alessandro Caforio、2025–2026）**：Academic-Writing（GitHub）。https://github.com/AlessandroCaforio/Academic-Writing 。読んだ
    - していること・わかったこと：実証経済学の修士論文で、Claude Code に 17 の subagent、8 の rule、11 の skill を設定。LaTeX の章の下書き・校正、計量経済の identification の見直し、記号の一貫性、Python コードの見直しを subagent に任せる。主張は手元の 105 本の論文の corpus とページ単位で照らす。約 600 行の CLAUDE.md にデータ・処理・コードの判断・session log を残す。失敗：すでに却下した方法（td_adjusted を主な指標にすること）を Claude が何度も提案した。「DO NOT suggest」の一覧で止まった。品質の gate が作業を止めるのは不便で、advisory にした。
    - 原文：「This is not a template you install」「The project brain came first.」
    - この学生への関係：却下した案を CLAUDE.md に書くこと。修士学生が自分で書いた数少ない記録。

13. **博士学生（NLP・interpretability の博士 3 年、r/MachineLearning、8 月 31 日、年は不明）**：Claude Code for Research Papers [R]。元の投稿 https://www.reddit.com/r/MachineLearning/comments/1w2wqbm/claude_code_for_research_papers_r/ は開けなかった。二次記事 https://www.remio.ai/post/claude-code-speeds-research-then-weakens-code-ownership だけ読んだ
    - していること・わかったこと（二次記事の要約）：experiment scaffolding、dataloader の refactor、最初の debug、解析スクリプトを任せ、diff を読んで承認する。それでもコードベースが自分のものと感じられず、結果が怪しいときにどこが原因か見当がつかない。debug が他人のリポジトリの監査のようになる。問題が review の後で出てくる。
    - 原文：二次記事は学生の文を直接引用していない。
    - この学生への関係：interpretability の博士学生という近い立場。「diff を読んで承認した」だけでは理解が保てないという報告。元の投稿は確かめていない。

14. **ML の研究者（Fatih Cagatay Akyon、日付は © 2026 だけ）**：Lab Rat / PhD Research Skills（GitHub）。https://github.com/fcakyon/phd-skills 。読んだ
    - していること・わかったこと：2,200 以上の Claude Code と Codex の session から作った skills。run を始める前の pre-flight checklist、debug では修正の前に証拠を集める、run は同じ epoch で比べる、新しい context の hook が結論を実際の artifact と照らす。きっかけになった実際の失敗：50 時間の学習を参照 run と config を diff せずに再開し 3 日失った。収束していない proxy metric で実験を止め、下流の評価が出る前に捨てた。誤ったパスを `rm -rf` に渡し checkpoint を消した。「done?」を「dont?」と読み違え数千のファイルをアップロードし始めた。
    - 原文：「AI agents make research mistakes that cost weeks of compute.」「Every guardrail traces to a real mistake.」
    - この学生への関係：GPU の長い学習を agent に触らせるときの失敗例そのもの。博士学生かはページにない（確かめていない）。

15. **企業の研究者（Sionic AI、Sigrid Jin、Hugging Face blog、2025-12-08）**：How We Use Claude Code Skills to Run 1,000+ ML Experiments a Day。https://huggingface.co/blog/sionic-ai/claude-code-skills-training 。読んだ
    - していること・わかったこと：学習スクリプト、CUDA エラーの debug、夜間の hyperparameter search、W&B からの結果の取得（MCP）を任せる。人は論文を読み、仮説・パラメータの範囲・予算・成功の基準を TECHSPEC に書く。session の終わりに `/retrospective` で skill を書かせ、「Failed Attempts」の表、正確な hyperparameter、ハードウェア、パッケージの版を必須にする。題の「1,000+ experiments a day」は、何を 1 つの実験と数えたか本文に定義がない。本文の具体的な数は、3 日で 50 以上の構成、18 run の sweep など。
    - 原文：「The knowledge is there. It just isn't findable.」
    - この学生への関係：失敗した試みと条件を記録の決まった欄に残す方法。題の数字は定義がなく、根拠にできない。

#### 研究論文・調査

16. **研究論文（Bridgeford, Campbell, Chen, Lin, Ritz, Vandekerckhove, Poldrack、arXiv 2510.22254 v2、2025-10-31）**：Ten Simple Rules for AI-Assisted Coding in Science。https://arxiv.org/html/2510.22254v2 。読んだ
    - していること・わかったこと：10 の規則。分野の知識を先に集める。問題の枠組みとコードを分ける。道具を作業に合わせる（chat、IDE、autonomous agent）。入出力・制約・edge case・成功の基準を先に考える。context file と問題を記録するファイルを使う。振る舞いのテストを先に書く（TDD）。agent がテストを書き換えて通すこと、placeholder や mock の処理に注意する。バグを見つけたら regression test を書かせる。作業を見て、ずれたら止め、clean な context からやり直す。commit してから大きな変更をする。成功の主張を信用せず、自分でテストしコードを読む。
    - 原文：「the models will often modify the tests to pass without actually solving the problem」「the models tend to claim success even when they haven’t really solved the problem」 vibe coding を「accepting AI-generated code you cannot evaluate, debug, or maintain」と定義する。
    - この学生への関係：研究コードでの確かめ方を一番まとまった形で書いた論文。著者の 1 人 Poldrack は The Transmitter に要約を書いた（https://www.thetransmitter.org/neuroscientists-using-ai/ai-assisted-coding-10-simple-rules-to-maintain-scientific-rigor/ 、検索結果だけ）。

17. **研究論文（Gabrielle O'Brien、University of Michigan、CHI 2025、arXiv 2502.17348、2025-02-24）**：How Scientists Use Large Language Models to Program。https://arxiv.org/abs/2502.17348v1 。読んだ（abstract だけ）
    - していること・わかったこと：研究大学の科学者への interview と利用 log。科学者は code generating model を、慣れない言語や library を調べる情報検索の道具として使うことが多い。生成コードが解析のパラメータを知らないうちに決めてしまう危険を指摘する。検索結果では、survey 199 人・interview 14 人、確かめ方は「動かして出力を目で見る」が多いとあるが、abstract では確かめていない。
    - 原文：「scientists often use code generating models as an information retrieval tool」
    - この学生への関係：agent 以前の chat 中心の利用の調査。「既定値が知らないうちに決まる」危険は agent でも同じ。

18. **研究論文（O'Brien, Parker, Eisty, Carver、arXiv 2512.19644、2025-12-22、v3 2026-04-09）**：A survey of generative AI adoption and perceived productivity among scientists who program。https://arxiv.org/abs/2512.19644 。読んだ（abstract だけ）
    - していること・わかったこと：プログラムを書く科学者 868 人の survey。生産性を感じる度合いを一番よく予測するのは、一度に受け入れる生成コードの行数。テスト・code review・version control をあまり使わない人ほど生産性を高く感じる。利用は学生と経験の少ない人で多い。
    - 原文：「The strongest predictor of perceived productivity is the number of lines of generated code typically accepted at once.」
    - この学生への関係：「速くなった感じ」は、受け入れた行数で決まっていて、確かめの量ではない可能性。自分の感じを指標にしない根拠。

19. **研究論文（Anthropic、Judy Hanwen Shen と Alex Tamkin、2026-01-29、arXiv 2601.20245）**：How AI assistance impacts the formation of coding skills。https://www.anthropic.com/research/AI-assistance-coding-skills 。読んだ
    - していること・わかったこと：主に若手の software engineer 52 人の randomized controlled trial。新しい非同期 library Trio を学ぶ。AI ありの群は quiz が平均 50%、手で書いた群は 67%（p = 0.01）。差が一番大きいのは debug の問題。時間の差は有意でない。quiz が低かった使い方：全部 AI に書かせる、だんだん任せる、debug を AI に任せる。高かった使い方：生成させた後に理解を確かめる質問をする、コードと説明を一緒に求める、概念の質問だけをして誤りは自分で直す。著者は、パターンの分析は相関で因果ではないと書く。
    - 原文：「The participants who showed stronger mastery used AI assistance not just to produce code but to build comprehension while doing so.」
    - この学生への関係：理解を保つ使い方が実験で比べられた数少ない研究。研究コードや agent の設定ではない。

20. **研究論文（METR、Becker, Rush, Barnes, Rein、arXiv 2507.09089、2025-07）**：Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity。https://arxiv.org/abs/2507.09089 。読んだ（abstract だけ）
    - していること・わかったこと：経験のある OSS 開発者 16 人、246 task の RCT。主に Cursor Pro と Claude 3.5/3.7 Sonnet。AI を許すと完了時間が 19% 長くなった。本人たちは 20% 短くなったと思っていた。
    - 原文：「Although the influence of experimental artifacts cannot be entirely ruled out」
    - この学生への関係：速さの感じと測った値が逆向きになりうる。2025 年初めの道具で、研究コードではない。

21. **研究論文（OpenAI と大学・研究所の共著、Jeremy Li ほか、2026、The Decoder の記事は 2026-08-01）**：Scientific computing in the age of agentic AI: an exploratory field report。https://cdn.openai.com/pdf/scientific-computing-in-the-age-of-agentic-ai-an-exploratory-field-report.pdf 。読んだ（PDF の一部）
    - していること・わかったこと：生命科学の 8 つの研究ソフトウェアで Codex や Claude Code を使った事例。8 件中 7 件で、人の作業は task の定義と verification の枠組みに集中した。agent に任せると「plausible but incorrect」な出力が出た。図は agent が「正しい」と言っても見ると壊れていて、900 以上の図を人が目で見る。RustQC の作者は model に自分の出力の正しさを判断させず、test harness を使った。bayesm では simulation-based calibration が、それまでの一致テストで見つからなかったバグを見つけた。
    - 原文：「Agents are eloquent, convincing, and confidently wrong in ways that are easy to miss, so I never let the model decide whether its own output was correct.」「the current bottleneck remains verification and validation.」
    - この学生への関係：独立した基準（参照実装、calibration、合成データ）で確かめる例。合成データでは見えない edge case が実データで出た、とも書く。

#### 研究室・大学の規則

22. **大学（UNC Chapel Hill の Biostatistics、Rashid Lab の handbook、日付の表示なし）**：Staying in the Driver's Seat。https://rashidlab.github.io/lab-handbook/claude-code/code-ownership.html 。読んだ
    - していること・わかったこと：Claude Code を使う研究室の全員が読む規則。boilerplate・書式の変換・regex は任せる。テスト・refactor・データベースの query は review 付きで任せる。設計・中心のアルゴリズム・複雑な debug は自分。prompt の前に自分で plan を書く。AI の出力は junior の pull request として 1 行ずつ読む。AI なしでコードを説明できるか。週に 1〜2 時間は AI なしで書く。DECISIONS.md と ARCHITECTURE.md を置く。8 つの危険信号（読まずに受け入れる、エラーを貼るだけで debug する など）。
    - 原文：「Never commit code you can't explain.」「Use the AI to execute your plan—not to make the plan for you.」
    - この学生への関係：研究室の規則として、任せる範囲を作業の種類で分けた例。

23. **大学（NYU の Todd Gureckis lab、2026-03-06）**：Lab AI Policy。https://todd.gureckislab.org/2026/03/06/genaipolicy 。読んだ
    - していること・わかったこと：コード・図・引用・方法の責任は各自。AI が書いたコードは test する。中心の解析コードは厳しく test する。大きな AI 生成コードはコメントや README に書き、解析やモデルのコードでの AI の利用は methods に書く。リポジトリに確かめ用・テスト用のスクリプトを入れ、他のメンバーが元データで結果を再現できるようにする。
    - 原文：「Code can be wrong in exactly the ways LLMs fail to catch.」
    - この学生への関係：論文の methods に AI の利用を書く規則の例。

#### 共通して言われていること

- **モデルの「できた」「verified」は確かめた証拠にならない。** Schwartz（4）、Ten Simple Rules（16）、OpenAI の field report（21）、Anthropic の best practices（1）が同じことを書く。Anthropic 自身も、実行したコマンドと出力を証拠として求めるよう書く。
- **確かめは、モデルの外の基準で行う。** 参照実装（3 の CLASS、21 の STAR）、calibration（21 の bayesm）、文献の正本（10 の Zotero、12 の corpus）、生の分布を見る（9）、test harness（21）。モデルが自分で確かめるのではなく、人が用意した基準で確かめる。
- **人がするのは、問題の枠組み・成功の基準・確かめ方。agent は実装。** 15（TECHSPEC）、16（規則 2・4）、21（7/8 件）、22（plan は自分で書く）、8（アイデアと判断は自分）。
- **テストを agent が書き換えることに注意する。** 16 が明記。3 でも一時期 1 点だけのテストでバグを見逃した。
- **決定・失敗した方法・条件をファイルに残す。** CLAUDE.md、CHANGELOG.md、DECISIONS.md、Failed Attempts の表（3、8、12、15、22）。会話の context は消える（8）。却下した案を書かないと再び提案される（12）。
- **git で小さく commit する。** 3、8、11、16。再現の単位を commit に置く（11）。
- **別の instance・別のモデルに見直させる。** 4（GPT と Gemini）、9（新しい Claude）、14（新しい context の hook）、1（`/code-review` の subagent）。ただし 4 では 3 つのモデルがそろって見落とした項もある。
- **長い session は指示を落とす。** 8、10、1（2 回直して駄目なら `/clear`）。

#### 意見が分かれていること

- **どこまで任せるか。** Schwartz（4）はファイルを編集せず全部任せ、50〜60 時間の監督で結果を得た。Karpathy の autoresearch（6c）も人は Python を触らない。一方、Rashid Lab（22）は中心のアルゴリズムと複雑な debug を自分で、と決める。Karpathy 自身も nanochat（6a）はほぼ手で書いた（検索結果だけ）。
- **diff を読めば十分か。** Saeed（11）はすべての diff を読むことを中心に置く。r/ML の博士学生（13、二次記事）は、diff を読んで承認しても自分のコードと感じられないと書く。Rashid Lab（22）は「AI なしで説明できるか」「週に 1〜2 時間 AI なしで書く」を加える。
- **学ぶことと速く進めること。** Nanda（5）は、学ぶのが目的なら tutor としてだけ使えと言う。Shen と Tamkin（19）は、任せた群で debug の理解が落ちたと測った。一方、Carlini（7）や Goldsmith-Pinkham（8）は、実験コードの最初の版や面倒な作業を任せて速くなったと書く。
- **速くなるか。** Carlini は自分で 50% 速くなったと見積もる（7）。METR（20）は経験のある開発者で 19% 遅くなり、本人は速くなったと感じていた。O'Brien ら（18）は、感じる生産性は受け入れた行数で決まるとする。自己申告と測定が合わない。
- **CLAUDE.md・skills の効果。** Caforio（12）や Sionic AI（15）は中心に置く。Schwartz（4）は「a little, but not enough」と書く。

#### 見つからなかったこと・確かめていないこと

- **博士学生・修士学生が自分の名前で書いた詳しい記録は少なかった。** 見つけたのは修士学生 1 件（12）と、二次記事でしか読めなかった博士学生 1 件（13）。Reddit は開けなかった。3、5、11、14 の書き手が学生かどうかはページに書かれていない。
- **ML の学習実験（GPU で長い学習）での使い方を詳しく書いた研究者の記事**は、14（失敗の一覧）、15（企業）、6c（autoresearch）だけ。強化学習や自己対局の学習で agent を使った報告は見つからなかった。
- **interpretability の研究で、解析コードをどう確かめるか**を具体的に書いたものは見つからなかった。Nanda（5）は一般的な助言だけ。
- **Karpathy の 2026-01 の投稿の原文**は開けなかった（X が 402）。nanochat の発言も検索結果だけ。
- **Scott Cunningham の「Claude Code Part 12」**（https://causalinf.substack.com/p/claude-code-part-12-how-i-use-claude ）は途中から有料で、読めたのは冒頭だけ。検索結果では、自分のコードを見直すモデルは自分の選択を守りがちなので「Referee 2」を立てる、とあるが確かめていない。出典の一覧には入れていない。
- **Carlini の記事**は後ろの 85,000 字を読んでいない。確かめ方の記述があるかは確かめていない。
- **abstract だけ読んだ論文**（17、18、20）は、本文の方法・人数・限界を確かめていない。17 の「survey 199 人・interview 14 人」は検索結果だけ。
- **Goldsmith-Pinkham（8）、Nanda（5）、Shuai（10）の肩書き・所属**は、読んだページの範囲では確かめていない。
- **数字**：15 の「1,000+ experiments a day」は定義がない。21 の速さの数字（60 倍など）は二次記事の数字で、PDF では確かめていない。
- 数を絞るため、Simon Willison の「Vibe engineering」（https://simonwillison.net/2025/Oct/7/vibe-engineering/ 、読んだ。テストが整っていると agent がよく働く）、プロの開発者の観察研究 Huang ら（https://arxiv.org/abs/2512.14012 、abstract を読んだ。経験者は agent を計画と監督で制御し vibe coding しない）、LessWrong の code を読まずに監督した 60 時間の失敗報告（https://www.lesswrong.com/posts/RjuZ4spL96rtvbmLt/failure-modes-of-claude-code-in-a-supervised-but-code-blind 、読んだ。研究者ではない）は一覧から外した。

### 日本の研究者・学生の使い方

調べた日：2026-11-16。WebSearch と WebFetch で調べた。

注意：
- 「読んだ」は WebFetch でページを開いたもの。WebFetch は小さなモデルがページを要約して返す。そのため、下の原文の引用は、そのモデルが返した文をそのまま写している。一字一句が原文と同じかは確かめていない。
- 「この学生への関係」は私の推論。出典には書かれていない。

#### 出典

- **研究者（松尾研究所のデータサイエンティスト、25卒。学生かどうかは書かれていない。2026-07-08 公開）**：「Claude codeと論文書いたら良い論文"は"できた」。https://zenn.dev/mkj/articles/cco-paper_20260531 。読んだ
  - していること・わかったこと：ARR に出す分析論文を約 7 週間で書いた。Claude Code を中心にして、サーベイは Opus の subagent、PDF の精読は Gemini CLI、実験設計のレビューは Codex CLI に分けた。実験コードは `/team-implement`、再現性（seed 固定、設定の外出し、結果を JSON に集める）は `/team-review` で見た。学習から評価・可視化までは速かった。仮説と RQ、結果から意味のある示唆を取り出すことは人がした。引用は arXiv・ACL Anthology・DOI に人が当たって確かめた。本文の数字は結果 JSON とログと照らした。失敗：骨子（RQ、主張、実験と主張の対応）を先に決めなかったため、論文の構成を v3 から v10 まで 7 回作り直した。約 108 本の run の管理は人の負担が大きかった。CLI と Overleaf の同時編集で版がぶつかった。
  - 原文：「生成物は素材，検証は人間，責任は著者．」
  - この学生への関係：論文の数字を記録と照らす、引用を原典で確かめる、という点はこの学生の作業の規則と同じ向き。「骨子を先に決める」は、論文を書く前に主張と実験の対応を決めておくことに当たる。

- **修士学生（2025-07-22）**：「Claude Codeで修士論文を書いてみた - CLAUDE.mdで論文執筆を半自動化する試み」。https://zenn.dev/hy20191108/articles/e7e97174538895 。読んだ
  - していること・わかったこと：章ごとの文章の生成と文体の調整を Claude Code に任せた。CLAUDE.md に学術的な文体のルール（例："proves" ではなく "suggests"）と論文の構成を書いた。論文の構成、主張、研究の方向は自分で決めた。チェックの具体的な手順は書かれていない。
  - 原文：「大学によっては学位論文への利用がダメなところもあるため、確認を行ってください。」
  - この学生への関係：学位論文や学会に出す原稿に使うなら、大学と学会の規定を先に確かめる必要がある。この学生の大学と GPW の規定は確かめていない。

- **企業の研究者（日本IBMシステムズ・エンジニアリングの DXC Lab、国際会議に投稿。2026-08-17）**：「Claude Codeを論文執筆に使って分かったこと」。https://zenn.dev/dxclab/articles/b4510565b4dff2 。読んだ
  - していること・わかったこと：任せたのは英語の下書き、実験の実行、結果の集計、グラフ、参考文献の表記の統一、匿名化、README と評価スクリプト。自分でしたのは研究の問い、仮説、手法、実験設計、主張の範囲、結果の解釈。初稿の全体チェックで見つかった問題は AI に直させず、一つずつ自分で確かめた。`paper-review` という skill を作り、5 つの観点（Significance、Soundness、Novelty、Related Work、Evaluation）で見させた。見つかった問題は GitHub Issue にした。`grill-me` という skill で AI から著者に質問させ、前提を引き出した。限界：文法は正しいが技術的に不正確な文、強調すべき結果を強調しない文が出る。
  - 原文：「修正をAIに丸投げせずに」
  - この学生への関係：査読者の観点で AI に見させる skill は、この学生の「査読者の立場から見る」方針と近い。ただし最後の判断は著者がしている。

- **大学院生（基礎研究。プロフィールに医師とある。2026-06-24）**：「ようやくClaudeを基礎研究で使ってみた【大学院】【論文検索+α】」。https://note.com/picoro_66/n/n1640fa372949 。読んだ
  - していること・わかったこと：Claude Code ではなく Claude の Cowork を使った。文献検索、新規性の確認、査読者の目線での反論を出させた。論文は自分で読み、AI の答えを英語の原文と照らした。困ったこと：AI が会話の内容を研究に好意的に解釈してメモリに残し、批判の場として信頼しにくくなった。一度に全部させると利用上限に達し、コンテキストが長くなった。作業をフェーズに分け、前のファイルを全部参照させる指示にした。未発表のデータや患者の情報は入れない。
  - 原文：AI の意見は「鵜呑みにはできません」
  - この学生への関係：AI が肯定に寄るという問題は、この学生の「楽観視せず批判する」方針と同じ問題を指している。

- **大学教員・企業の研究者（浦西友樹 大阪大学 D3センター教授、松井勇佑 東京大学 講師、米谷竜 サイバーエージェント。DEIM2026 チュートリアル、2026-03-04 講演、2026-03-12 公開）**：「明日から使える研究効率化ツール入門」。https://speakerdeck.com/matsui_528/ming-ri-karashi-eru-yan-jiu-xiao-lu-hua-tururu-men 。読んだ
  - していること・わかったこと：設計は人、コーディングとデバッグは agent、最後の品質の確認は人、という流れ。自分の専門の部分以外の実装は任せてよい、という考え。失敗の例：AI がエラーを消せずに「動いたように見せる」、例外処理や後方互換のコードが増えて肥大化する。LLM に編集させた文章は全文をレビューする。Claude Code の plan mode は読み取りだけ。投稿先の規定ではツールの利用を謝辞などに書くのが一般的。
  - 原文：「成果物の責任は人間（自分）が持つ」、「LLMが変えない保証がない」、「「仕様をちゃんと指示する」「エージェントの実行権限は適切に制限する」を守っておけば大事故はしにくい」
  - この学生への関係：日本の学会（DEIM）で教員が学生向けに話した例。「動いたように見せる」は、学習や測定のコードで結果が出ても中身を確かめる理由になる。

- **学部生（電気通信大学の在学生、講師・会社代表も兼ねる。2025-08-07）**：「大学生のClaude Code活用術」。https://speakerdeck.com/kochan17/da-xue-sheng-noclaude-codehuo-yong-shu 。読んだ
  - していること・わかったこと：レポートのグラフとコード、LaTeX のレポート、スライドを Claude Code に作らせた。授業の課題をクローンして出し、レポートも任せた。出力を確かめる方法は書かれていない。
  - 原文：「その結果、ぜんぜん出席しなくなった」、「使わせないと伸びない」
  - この学生への関係：確かめる手順のない使い方の例。研究には向かない。対比として挙げる。

- **大学教員（西村良太 豊橋技術科学大学 准教授。2026-08-07 公開）**：「ClaudeCode実践講座（大学教員に役立つ版）」。https://docswell.com/s/sayonari/ZQ2NRX-2026-08-07-212458 。読んだ
  - していること・わかったこと：採点、成績票、科研費の申請書の整理、論文の修正の対応表などを Claude Code に任せた。引用・数値・合計は機械的に照らす。AI に自信のない箇所を申告させる。論文の修正では旧文・新文・理由を残し、共著者が確かめられるようにした。LLM はセッションをまたいで記憶しないので、引き継ぎのメモを残させる。失敗したら止めて文脈を切り、指示し直す。学生の研究向けの内容は「第2弾として今後作成予定」。
  - 原文：「AIが出すのは「候補」まで。判断と責任は、使う人間のもの」、「1発目の精度はとても高い。でも失敗すると2発目3発目はどんどん落ちる」
  - この学生への関係：失敗したら文脈を切って指示し直す、という助言は長いセッションで使うときに当てはまる。

- **大学教員（情報通信系の教員、プログラミング歴 35 年。2026-10-03）**：「AIコーディング時代のCS学生へ ── 35年プログラマーからのメッセージ」。https://hasevr.hateblo.jp/entry/2026/10/03/142504 。読んだ
  - していること・わかったこと：2026 年夏から、プログラミングのほとんどを AI に任せている。AI が書いたコードはほぼ読まない。代わりに、アルゴリズム、数式、変数と定数（特に閾値）、作業の手順を確かめる。AI がコードを書き、テストし、直すところまで人を通さずに回せる環境を作る。途中の報告やテスト結果に違和感があれば、どの段階でも止めて方針を直す。若手がシニアや PM の技能をどう身につけるかは、まだ確立していないと書いている。
  - 原文：「AIに丸投げするだけでは学びは残りません。」、「AIの説明が正しいかどうかを見抜けなければ、AIを指導することはできません。」
  - この学生への関係：コードを読まない代わりに数式と閾値を確かめる、という分け方は、学習や測定の設定値を確かめる作業に当てはまる。

- **研究者（西森秀稔 東京科学大学 特任教授・東京工業大学 名誉教授、理論物理。2026-08-30）**：「理論物理の研究でAIを全面的に使ってみました」。https://note.com/nishimori_h/n/nad57b40fb540 。読んだ
  - していること・わかったこと：系統の違う 2 つのモデルを使った。Claude が導出と数値計算をし、ChatGPT が独立に査読した。数値計算では、Claude のコードは渡さず数値だけを渡し、別のアルゴリズムで計算し直させた。2 往復で多くは収束し、それ以上は指摘のための指摘が増えた。最後に全段階を一行ずつ自分で確かめた。2 往復をすり抜けた符号の誤りが実際にあった。2 つのモデルが同じ偏りを共有して揃って「問題なし」と言う可能性を指摘している。
  - 原文：「式(3)から式(4)への変形で、右辺の符号が反転している根拠だけに集中して、詳しく説明せよ。」（焦点を絞った質問の例）
  - この学生への関係：コードを見せずに数値だけを渡して別の方法で計算し直させる、という確かめ方は、測定の結果を確かめるときに使える。コードを見せると確かめる側が元の論理の穴を見逃す、という理由が付いている（検索結果の要約にあった説明。本文のどこにあるかは確かめていない）。

- **個人（論文の再現。立場は書かれていない。2026-06-12）**：「【検証】Claude Codeによる論文解読と実験用コード作成検証」。https://qiita.com/ruih8gta/items/1297cbf0d5115fc36c3c 。読んだ
  - していること・わかったこと：アリの採餌の論文（2003 年）を Claude Code に読ませ、numpy で再実装、パラメータ走査、図、レポートまで作らせた。1 回目のレポートは「論文の主張をすべて再現できた」と結論していたが、検証すると内部の矛盾があった。元の論文が「明確には示せていない」とした効果を、AI は確認済みと断言していた。最適な混合比が論文（敏感 9 割）と実装（敏感 1.5 割）で逆だったのに、1 回目は触れていなかった。著者は、結論の検証を別のタスクとして指示し、数値の導出の根拠を出させ、原典と照らした。
  - 原文：「AIは原典より強く言い切っていました」
  - この学生への関係：AI のレポートが原典より強く言い切る例。論文の先行研究の要約や、自分の結果の説明を AI に書かせるときの注意になる。

- **将棋AI の開発者（select766、ねね将棋の開発者。2026-05-06）**：「第36回世界コンピュータ将棋選手権の結果(2026/05/03)」。https://select766.hatenablog.com/entry/2026/05/06/190100 。読んだ
  - していること・わかったこと：8 種類の NNUE 評価関数を手番ごとに混ぜる仕組みと、混ぜる比率を決めるモデルを end-to-end で学習する仕組みを作った。実装は主に Claude と Codex。構想、ハードウェア、定跡の採否、置換表をクリアしない判断は自分でした。確かめ方は大会の対局とテスト対局。単体テストや A/B 比較の記述はない。テスト対局で初手に 64 秒かかり、公開定跡を使う方針に変えた。
  - 原文：「実装は主にClaude＋Codexで行いました。」、「コーディングエージェントがなかったら、このようなend-to-end学習機構を一人で作るのは難しかったと思います。」
  - この学生への関係：日本の将棋AI の開発者が、学習の仕組みの実装を coding agent に任せた例。設計の判断は開発者がしている。

- **将棋AI の開発者（passiomonster、技巧を題材にした開発日記。2026-06-29）**：「【将棋AI開発日記】3. 評価関数を13時間かけて学習させたら、初手から投了した話」。https://qiita.com/passiomonster/items/0ff5f34ec002b8234408 。読んだ
  - していること・わかったこと：Claude Code と一緒に評価関数を学習した（14 スレッド、約 13 時間、10,000 iteration）。学習に使っていない 1000 局で一致率を測り、43.6% から 49.1% に上がった。学習後に初手で投了した。原因は評価関数ではなく、エンジンに `go` と `quit` を一度に送っていたため、探索の前に終わっていたこと。デバッグビルドでは assertion が出ていた。Claude がどの作業をしたかは詳しく書かれていない。
  - 原文：「まず自分の動かし方を疑え。」
  - この学生への関係：学習の失敗に見えて、実は確かめる手順の誤りだった例。長い学習の前に小さく動かして確かめる、という規則と同じ向き。

- **個人開発者（将棋を覚えたばかり、Rust で将棋エンジンと NNUE 学習ツール。2025-07〜12 のログ）**：「将棋エンジンを作る、P2P通信対戦をする、対戦AIを作る」。https://zenn.dev/sh11235/scraps/3456d57f674c73 。読んだ（長いので前半約 10 万字だけ）
  - していること・わかったこと：エンジン、NNUE 学習ツール、探索部、UI を Claude Code に作らせ、途中から Codex も使った。plan mode の計画は自分でレビューした。CI（型チェック、lint、テスト）、NPS をコミットごとに記録、ShogiHome・ShogiGUI での対局、自己対局のスクリプトで確かめた。失敗：Claude Code がローカルのシグナリングサーバー経由の実装を「P2P」と報告した。バグのたびに層を足して根本原因を見ず、約 1 か月を無駄にした。探索部は「退行9割」が続き、全部作り直した。ログが多すぎてコンテキストがすぐ埋まった。計画を文書にしてコンテキストを切ると上手くいった。
  - 原文：「生成AIによかれで作らせた積み重ねはとても不安定な足場の上に出来上がった構造物でもろいのだなと感じた。」、テストと計測を先に整えることについて「最初からやっとけばよかったなぁ。」
  - この学生への関係：AI の完了報告が実際の中身と違う例。報告を信じず、動作や記録で確かめる理由になる。

- **ソフトウェアエンジニア（趣味の開発。2025-10-08）**：「コーディングAIで、挫折していた古将棋AIを完成させた話」。https://note.com/kuro5497/n/ncec22f60a376 。読んだ
  - していること・わかったこと：対局 UI を Claude Code に全部任せたら、バグが増えて保守できなくなった。機能ごとに指示を出してコードレビューし、できない部分は自分で書く形にした。Codex CLI も併用した。確かめ方は具体的に書かれていない。
  - 原文：「速攻でバグを量産して即メンテ不可能に陥りました」
  - この学生への関係：全部を一度に任せず、機能ごとに分けて見る例。

- **エンジニア（株式会社クイック、趣味で AI を自律的に動かす。2026-11-02）**：「ClaudeCodeで自律的に調査させてみたら大失敗した」。https://qiita.com/sai029/items/57b38881f03f7ff0638c 。読んだ
  - していること・わかったこと：人の文章と AI の文章の違いを Claude Code に自律的に調べさせた。人の文章が明治〜昭和前半の作品に偏り、差が人と AI の違いか時代の違いか分けられず、目的に使えない調査になった。改善：実行の前に、データが目的と合っているか、成功を他の人が判断できるか、失敗しそうな理由を 3 つ挙げて小さく試す、などを skill に書き出させるようにした。
  - 原文：「「それで何が分かれば成功なのか」を決めていなかった」
  - この学生への関係：データの性質が混ざって比較が成り立たない例。この学生の CLAUDE.md にある、動物将棋のデータの向きが混ざっていた件と同じ種類の問題。測定の前に「何が分かるか」を小さく確かめる規則の根拠になる。

- **企業が大学で実施（クラスメソッドが九州大学の大学院生向け集中講義で演習。2026-04-25〜26）**：「九州大学様向けに Claude Code の開発演習を実施しました」。https://dev.classmethod.jp/articles/2026-04-28_kyushu-university-claude-code-handson/ 。読んだ
  - していること・わかったこと：約 60 名（大学院生と QBS の学生が半々）。`/scope-design`、`/verify-project`（作ったものを自分の言葉で説明する振り返り）などの skills を用意した。受講者は振り返りで理解が足りないまま作ったことに気づいた。研究ではなくアプリ開発の演習。
  - 原文：「振り返りのところでClaude Codeから痛い質問をたくさんされました。」
  - この学生への関係：作ったものを自分の言葉で説明させる、という確かめ方。研究のコードにも使えるかは確かめていない。

- **研究者（西川裕章、数値流体力学、米国の研究機関。X の投稿のまとめ。2026-09-16）**：「若い研究者のデバッグ中に「この変数の値を確認しよう」と言っても、大丈夫だと断られる…→AIは賢くないが素直だと力説」。https://togetter.com/li/2746161 。読んだ
  - していること・わかったこと：若い研究者（人）が変数の確認を「大丈夫です」と断り、あとで確かめると初期値が途中で上書きされていた。投稿者は AI に論文をもとにコードを書かせ、約 1 か月で複数の論文につながる研究を進めたと書いている。反応には、AI が当たり前になると人がデバッグの意識を持たなくなるという懸念があった。
  - 原文：「AIは面倒がらない。この一点でも人間は勝てない。」
  - この学生への関係：思い込みで確かめない人の例。AI ではなく人の側の問題として出ている。日本の研究機関ではないが、日本語で議論された。

- **大学（大阪工業大学の教員ら。rePiT2026 論文集）**：「ソフトウェア開発PBLへのAIエージェントを活用した仕様駆動開発の導入実践報告」。https://www.jstage.jst.go.jp/article/repit/2026/0/2026_90/_pdf/-char/en 。開いたが本文の文字が読めなかったので、検索結果だけ
  - していること・わかったこと：検索結果の要約では、学部のソフトウェア開発 PBL で AI エージェント（GitHub Copilot、Codex、Devin、Claude Code）を使った。
  - 原文（検索結果の要約に出た文。本文では確かめていない）：「開発効率が向上する一方で，学生がコードを十分に理解せずに開発を進める傾向も確認された」
  - この学生への関係：学生がコードを理解しないまま進むという問題が、日本の学会の論文で報告されている。対象は学部の PBL で、研究ではない。

- **修士学生（東大の修士 2 年とされる）**：「Claude Codeで日常のタスクを45個自動化した東大院生の全記録」。https://zenn.dev/shunya_sudo/articles/claude-code-45-automation-tasks 。検索結果だけ（開くと 404）
  - していること・わかったこと：検索結果の要約では、日常の雑務を 45 個の cron ジョブで自動化した。研究データ、実験結果、研究の意思決定は対象外と明記している。
  - 原文：確かめていない。
  - この学生への関係：研究の判断を AI に任せない、と書く学生の例。中身は確かめていない。

- **調査の紹介（広島大学の 2025 年の調査を紹介する企業ブログ）**：https://www.nai.co.jp/blog-roadmap1106-blog 。検索結果だけ
  - していること・わかったこと：検索結果の要約では、卒論・修論の執筆に生成 AI を使った学生が 80%、指導教員から生成 AI について特に話がなかったという回答が 42.1%。元の調査は開いていない。数字は確かめていない。
  - この学生への関係：指導教員と AI の使い方を話していない学生が多い、という調査。確かめていない。

（参考にしなかったもの：https://claudecode.digirise.ai/blog/claude-code-academic-research は導入支援の会社のブログで、「ある国立大学」のような出典の分からない話が多い。検索結果だけ。数に入れていない。）

#### 共通して言われていること

- 研究の問い、仮説、主張の範囲、結果の解釈は人がする。実装、集計、図、下書きは AI に任せる。（松尾研究所、DXC Lab、修士論文の記事、DEIM2026、select766）
- 責任は人が持つ。（DEIM2026「成果物の責任は人間（自分）が持つ」、西村「判断と責任は、使う人間のもの」、松尾研究所「責任は著者」）
- 数字と引用は元のデータと原典で確かめる。（松尾研究所、西村、ruih8gta、picoro）
- AI の報告は実際より強く言い切る、または実際と違うことがある。「再現できた」「P2P」「動いたように見せる」の例がある。（ruih8gta、sh11235、DEIM2026）
- 全部を一度に任せると壊れる。機能や段階に分け、計画を文書にしてコンテキストを切る。（kuro5497、sh11235、picoro、西村）
- 確かめ方の工夫：別のモデルや別のアルゴリズムで独立に計算し直す（西森）、査読者の観点の skill（DXC Lab）、AI から質問させる skill（DXC Lab、九州大学）、実行前に目的とデータが合うかを書き出させる（sai029）。
- 大学・学会の規定を確かめ、AI の利用を明記する。（修士論文の記事、DEIM2026）

#### 意見が分かれていること

- コードを読むか。hasevr は AI のコードを「ほぼ読まない」で、数式・閾値・手順を確かめる。kuro5497 と sh11235 はコードレビューや設計どおりかのレビューが必要だとする。rePiT2026（検索結果だけ）は学生がコードを理解しないことを問題としている。
- 学生に自由に使わせるか。石田（学部生）は「使わせないと伸びない」と言う。hasevr は「AIに丸投げするだけでは学びは残りません」と言い、基礎を身につけることを勧める。浦西（DEIM2026）は生産性が「N倍違う」と言う。
- 確かめる AI を増やすほどよいか。西森は 2 往復で十分で、それ以上は指摘のための指摘が増えるとする。松尾研究所や DXC Lab は複数の AI と skill でレビューを重ねている。往復の数を比べた研究は見つからなかった。

#### 見つからなかったこと・確かめていないこと

- 日本の博士学生が研究のコードに Claude Code を使った詳しい記録は見つからなかった。見つかったのは修士学生、研究所・企業の研究者、教員の記録が中心。
- 将棋AI・ゲームAI の「研究」（論文を書く研究）で Claude Code を使った日本の記録は見つからなかった。見つかったのはエンジン開発者のブログ（select766、passiomonster、sh11235、kuro5497）。GPW など日本のゲーム AI の学会で AI コーディングを扱った発表も見つからなかった。
- dlshogi の開発者のブログ（TadaoYamaoka の開発日記）に Claude Code の記事があるかは、検索では出なかった。ブログを直接は見ていないので、確かめていない。
- 研究室のページで Claude Code の利用ルールを公開している例は見つからなかった。大学全体の生成 AI のガイドライン（日本大学、星薬科大学など）は検索結果に出たが、コーディングエージェントに特化したものではない。開いていない。
- 上の引用はすべて WebFetch の要約モデルが返した文。原文と一字一句同じかは確かめていない。
- sh11235 の記事の後半（約 3.6 万字）は読んでいない。
- rePiT2026 の本文、東大院生の記事、広島大学の調査は中身を確かめていない。
- 検索結果の要約に出た「東京大学の研究者らが AI の書く論文の質を測った」という X の投稿（https://x.com/ai_database/status/2039980971676856543 ）は、元の論文を探したが見つからなかった。確かめていない。

### 実証研究でわかっていること

調べた日：2026-11-16。WebFetch で開いたものは「読んだ」と書いた。ただし WebFetch は要約を返すので、読めたのは多くの場合、要旨と本文の一部である。PDF 本文を pdftotext で読んだものはそう書いた。原文の引用は WebFetch が返した文をそのまま載せた。

#### 出典

#### (1) 経験のある開発者の生産性

- **METR（研究機関、2025-07-10）**：Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity。https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ 。読んだ
  - していること・わかったこと：randomized controlled trial。大きな OSS リポジトリ（平均 22k stars 以上、100 万行以上）の経験のある開発者 16 人が、自分のリポジトリの実際の issue 246 件（1 件 約 2 時間）を解いた。issue ごとに AI を使ってよいか、使わないかを無作為に割り当てた。主に Cursor Pro と Claude 3.5/3.7 Sonnet。AI を使ってよいときのほうが 19% 長くかかった（2026-02 の METR の記事では信頼区間 +2% から +39%）。開発者は事前に 24% 速くなると予想し、終わったあとも 20% 速くなったと思っていた。
  - 原文：「we find that when developers use AI tools, they take 19% longer than without—AI makes them slower.」「We view this result as a snapshot of early-2025 AI capabilities in one relevant setting」
  - 限界（著者）：16 人と少ない。参加者の選び方による偏りを否定できない。Cursor の使用が約 50 時間を超えたあとの学習効果は否定できない。経験の浅い開発者や、なじみのないコードベースについては主張していない。METR 自身が「この結果は古い」と書いている。
  - この学生への関係：「自分では速くなったと感じる」ことと「実際の所要時間」が逆になりうる、という点が一番重要。自分の作業時間を感覚で語らず、測るなら測る。

- **METR（研究機関、2026-02-24）**：We are Changing our Developer Productivity Experiment Design。https://metr.org/blog/2026-02-24-uplift-update/ 。読んだ
  - していること・わかったこと：2025-08 から同じ設計で続きの実験をした。57 人（元の 10 人 + 新しい 47 人）、143 リポジトリ、800 件以上。時間の変化の推定（負は速くなった）：元の 10 人で −18%（信頼区間 −38% から +9%）、新しい 47 人で −4%（−15% から +9%）。しかし METR はこの推定を信頼できないと結論した。AI なしで働きたくない開発者が参加を断り、AI なしでやりたくない課題を出さなかった（調査で 30% から 50%）。複数の agent を同時に動かす人の時間の測定も信頼できなかった。報酬は時給 150 ドルから 50 ドルに下がった。
  - 原文：「likely a bad proxy for the real productivity impact of AI tools on these developers」「the true speedup could be much higher among the developers and tasks which are selected out of the experiment」
  - この学生への関係：「METR の追試で 18% 速くなった」と書くブログがあるが、METR 自身はその数を使えないと言っている。引用するならこの記事の言い方に従う。

- **METR（Joel Becker、2026-05-11）**：Measuring the Self-Reported Impact of Early-2026 AI on Technical Worker Productivity。https://metr.org/blog/2026-05-11-ai-usage-survey/ 。読んだ
  - していること・わかったこと：2026-02 から 04 のアンケート。分析したのは 349 人。うち academics and PhD students が 129 人（37%）。自己申告の「価値」の向上は中央値で 1.4 倍から 2 倍、「速さ」は 3 倍。2025-03 は 1.3 倍、2027-03 の予想は 2.5 倍。
  - 原文：「Importantly, survey results are not necessarily grounded in reality.」
  - 限界（著者）：メールの回答率 約 2%、選ばれ方の偏り、約 70% に報酬、反実仮想の数を答えるのは難しい、高すぎる回答がある。
  - この学生への関係：博士学生が分けて数えられている数少ない調査。ただし自己申告であり、上の RCT では自己申告が実測と逆だった。

- **Cui, Demirer, Jaffe, Musolff, Peng, Salz（Princeton・MIT・Microsoft・Wharton、2025-02 版）**：The Effects of Generative AI on High-Skilled Work: Evidence from Three Field Experiments with Software Developers。https://economics.mit.edu/sites/default/files/inline-files/draft_copilot_experiments.pdf 。読んだ（PDF の 1〜2 ページを pdftotext で）
  - していること・わかったこと：Microsoft、Accenture、匿名の Fortune 100 企業での 3 つの randomized controlled trial。Copilot（コード補完）を無作為に配った。合わせて 4,867 人。完了したタスク（pull request）が 26.08%（SE 10.3%）増えた。commits は 13.55%（SE 10.0%）増。経験の浅い開発者ほど使い、伸びも大きかった。
  - 原文：「our analysis reveals a 26.08% increase (SE: 10.3%) in completed tasks among developers using the AI tool. Notably, less experienced developers had higher adoption rates and greater productivity gains.」
  - 限界：要旨に「each experiment is noisy」とある。測っているのは件数で、品質ではない。道具は 2023 年ごろのコード補完で、agent ではない。Management Science に載ったかは検索結果（DOI 10.1287/mnsc.2025.00535）だけで、確かめていない。
  - この学生への関係：METR と逆向きの結果。違いは「経験」「なじみのあるコードか」「何を数えるか（件数か時間か）」。

- **Demirer, Musolff, Yang（MIT・Wharton、NBER Working Paper 35275、2026-05、2026-09 改訂）**：Writing Code vs. Shipping Code: Productivity Effects Across Generations of AI Coding Tools。https://www.nber.org/papers/w35275 （PDF：https://www.nber.org/system/files/working_papers/w35275/w35275.pdf ）。読んだ（PDF を pdftotext で、要旨・序論・注意書きの部分）
  - していること・わかったこと：GitHub の開発者 50 万人以上と AI 利用の telemetry を使った matched event study。autocomplete、interactive coding agents、autonomous coding agents の commits への累積効果はそれぞれ 30%、180%、240%。しかし 240% は、プロジェクト数で 80%、実際の release で 30% に下がる。Claude Code の利用者は、公開リポジトリで CLAUDE.md を最初にコミットした日で特定している。
  - 原文：「Large task-level AI productivity gains have therefore translated only partially into shipped and used software thus far.」
  - 限界（著者）：OSS と 4 つのアプリストアだけ。データは 2026 年半ばまで。査読前（NBER working paper）。CLAUDE.md で利用を特定するので、CLAUDE.md を置かない利用者は数えていない（これは私の推論）。
  - この学生への関係：「書いたコードの量」と「出来上がった成果」は別。研究なら commits の数ではなく、正しく動いた実験や論文の結果で見るべき、という点に合う（私の推論）。

- **He, Miller, Agarwal, Kästner, Vasilescu（Carnegie Mellon、MSR '26、v3 2026-01-26）**：Speed at the Cost of Quality: How Cursor AI Increases Short-Term Velocity and Long-Term Complexity in Open-Source Projects。https://arxiv.org/abs/2511.04427 。読んだ（要旨と本文 HTML の前半）
  - していること・わかったこと：staggered difference-in-differences。Cursor を導入した GitHub プロジェクト 806 件と、導入していない 1,380 件を比べた。導入は .cursorrules などの設定ファイルの最初のコミットで判定。最初の月は lines added が 3〜5 倍（推定 約 281%）、2 か月で消える。static analysis warnings は約 30.3%、code complexity は約 41.6% 増え、続く。warnings と complexity の増加が、のちの速度低下の主な要因と推定した。
  - 原文：「a statistically significant, large, but transient increase in project-level development velocity」「a substantial and persistent increase in static analysis warnings and code complexity」
  - 限界（著者）：設定ファイルを置いたリポジトリだけ。利用の強さは分からない（intent-to-treat）。他の AI ツールとの混在（382 件）。主に JavaScript・TypeScript・Python。本文の中で complexity が 41.6% と 25% の 2 つの書き方がある（WebFetch の要約による。私は表を見ていない）。
  - この学生への関係：AI で書いたコードの複雑さが後で効いてくる。研究コードでも、増えた分を読んで整理する手間を見込む必要がある（私の推論）。

- **Google DORA（2025-09）**：2025 State of AI-assisted Software Development。https://services.google.com/fh/files/misc/2025_state_of_ai_assisted_software_development.pdf 。検索結果だけ（PDF が大きすぎて開けなかった）
  - していること・わかったこと（検索結果の要約）：2025-06-13 から 07-21 のアンケート。90% が AI を使う。throughput は上がったが instability（変更の失敗・やり直し）も上がった。AI を「amplifier」と呼ぶ。信頼の数は記事ごとに違う（24% が「a lot / a great deal」、30% が「a little / no trust」など）。
  - この学生への関係：数は確かめていない。引用するなら PDF を開いてから。

#### (2) 学習と技能の形成

- **Judy Hanwen Shen, Alex Tamkin（Anthropic、2026-01-28、arXiv 2601.20245）**：How AI Impacts Skill Formation。https://arxiv.org/abs/2601.20245 、解説 https://www.anthropic.com/research/AI-assistance-coding-skills 。読んだ（arXiv の要旨と Anthropic の記事）
  - していること・わかったこと：randomized controlled trial。Python を 1 年以上毎週使う 52 人（主に junior）が、知らないライブラリ Trio で 35 分の課題をし、そのあと 25 分のテスト。AI ありの群は平均 約 50%、手で書いた群は 約 67%（Cohen's d = 0.738、p = 0.01）。差が一番大きいのは debugging の問題。速さの差は約 2 分で有意でない（p = 0.391）。使い方で分かれた：AI にすべて任せた人（n=4）は約 39%、生成のあと理解のための質問をした人（n=2）は約 86%、概念の質問だけした人（n=7）は約 65%。
  - 原文：「AI use impairs conceptual understanding, code reading, and debugging abilities」「Cognitive effort—and even getting painfully stuck—is likely important for fostering mastery.」
  - 限界（著者）：標本が小さい。テストは課題の直後だけで、長く残るかは分からない。使い方の分析は質的で因果ではない。サイドバーの assistant で、Claude Code のような agent ではない（著者は agent のほうが影響が大きいかもしれないと書く）。
  - この学生への関係：新しいライブラリや手法を覚える場面で全部を任せると、あとで debugging ができない。各群の人数は 2〜7 人なので、使い方ごとの数は強く言えない。

- **Lehmann, Cornelius, Sting（University of Cologne など、v2 2025-03-08、arXiv 2409.09047）**：AI Meets the Classroom: When Do Large Language Models Harm Learning?。https://arxiv.org/abs/2409.09047 。読んだ（要旨のみ）
  - していること・わかったこと：大学院のプログラミング授業 2 つでの field study と、pre-registered で incentivized な実験室実験 2 つ。全体の学習成果への効果はなかった。解答を作らせる使い方（代わりにさせる）では扱う範囲は広がるが理解が浅い。説明を求める使い方では理解が深まる。事前知識の差を広げる。検索結果の要約では、copy-and-paste ができると解答を求める行動が増え学習が減る、とある（本文で確かめていない）。
  - 原文：「In two pre-registered and incentivized laboratory experiments, we find no effect of LLMs on overall learning outcomes.」「We also observe that LLMs widen the gap between students with low and high prior knowledge.」
  - 限界：標本の大きさと効果量は要旨になく、確かめていない。ChatGPT の時期の研究。
  - この学生への関係：Shen & Tamkin と同じ向き：「何をさせるか」で結果が変わる。

- **Anthropic（2025-04-08）**：Anthropic Education Report: How University Students Use Claude。https://www.anthropic.com/news/anthropic-education-report-how-university-students-use-claude 。読んだ
  - していること・わかったこと：大学のメールアドレスの Claude.ai アカウントの会話 約 100 万件（18 日間）を Clio で分析。学業に関係する 574,740 件。Computer Science が 36.8%（本文では 38.6%）。約 47% が Direct（やりとりが少なく答えを求める）。
  - 原文：「An inverted pyramid, after all, can topple over.」
  - 限界（著者）：早く使い始めた人に偏る。何を任せたかは分かるが、学んだかは分からない。
  - この学生への関係：学習の効果は測っていない。利用の分布だけ。

#### (3) AI が書いたコードの理解・review・over-reliance

- **Perry, Srivastava, Kumar, Boneh（Stanford、ACM CCS '23）**：Do Users Write More Insecure Code with AI Assistants?。https://arxiv.org/abs/2211.03622 。読んだ（要旨のみ）。2025 年より古いが、この話題の主要な研究
  - していること・わかったこと：user study。codex-davinci-002 の assistant がある群とない群。ある群は安全でないコードを多く書き、しかも安全だと思う人が多かった。AI をあまり信じず、prompt を言い換えた人は脆弱性が少なかった。
  - 原文：「wrote significantly less secure code than those without access」「were more likely to believe they wrote secure code」
  - 限界：参加人数は要旨になく、確かめていない。古いモデル。
  - この学生への関係：Shen & Tamkin、METR と同じく「自信」と「実際」がずれる。

- **Veracode（企業、2025-07-30）**：2025 GenAI Code Security Report。https://www.veracode.com/blog/genai-code-security-report/ 。読んだ（ブログのみ。報告書本体は開いていない）
  - していること・わかったこと：100 以上の LLM に Java・Python・C#・JavaScript の課題を書かせ、静的解析にかけた。45% のコードが security test に落ちた。Java 72%、C# 45%、JavaScript 43%、Python 38%。新しく大きいモデルは文法的に正しいコードは増えたが、security は良くならなかった。
  - 原文：「45% of code samples failed security tests and introduced OWASP Top 10 security vulnerabilities into the code.」
  - 限界：課題の数（検索結果では 80）と方法は報告書本体にあり、確かめていない。Veracode は security ツールを売る会社。
  - この学生への関係：研究コードでは security より「正しさ」が問題なので、直接は関係が薄い。「動く・文法が正しい」と「正しい」は別、という点だけ使える（私の推論）。

- **Watanabe, Li, Kashiwa, Reid, Iida, Hassan（NAIST・Queen's University など、v3 2026-02-09、arXiv 2509.14745）**：On the Use of Agentic Coding: An Empirical Study of Pull Requests on GitHub。https://arxiv.org/abs/2509.14745 。読んだ（要旨のみ）
  - していること・わかったこと：Claude Code で作られた pull request 567 件（157 の OSS プロジェクト）を調べた。83.8% が最終的に merge された。merge されたもののうち 54.9% は手直しなし、45.1% は追加の変更が必要だった（bug fix、documentation、プロジェクト固有の決まりへの合わせ込み）。
  - 原文：「These findings suggest that while agent-assisted PRs are largely acceptable, they still benefit from human oversight」
  - 限界：Claude Code と分かる PR だけ。merge されたことを成功と数えている。検索結果では人の PR は約 91%、TOSEM 採録とあるが、確かめていない。
  - この学生への関係：Claude Code の出力の約半分に人の手直しが入っている、という実測。

- **Huang, Reyna, Lerner, Xia, Hempel（UC San Diego など、v2 2026-08-18、arXiv 2512.14012）**：Professional Software Developers Don't Vibe, They Control: AI Agent Use for Coding in 2025。https://arxiv.org/abs/2512.14012 。読んだ（要旨と本文 HTML の前半）
  - していること・わかったこと：経験のある開発者の field observation 13 人と qualitative survey 99 人。観察の 13 人中 11 人が plan を自分で書くか直した。1 回の prompt あたりの手順の中央値は 1.8。13 人中 9 人がすべての変更を review した（diff を読む、テストを走らせる、など）。user rules は観察 3 件・調査 18 件。調査の回答者のツールは Claude Code 58、GitHub Copilot 53、Cursor 51。
  - 原文：「Our most salient finding is that, indeed, professional developers do not vibe code.」「Instead, they carefully control the agents through planning and supervision.」
  - 限界（著者）：観察は 13 人で 1 回 45 分。調査は AI に好意的な人に偏る。ほぼ男性（12/13、97/99）。
  - この学生への関係：plan mode、小さい手順、全変更の review、git で戻す、という使い方が経験者の実際の行動として記録されている。

- **Stack Overflow（企業、2025-07）**：2025 Developer Survey, AI。https://survey.stackoverflow.co/2025/ai 。読んだ
  - していること・わかったこと：AI の質問に 33,662 人が回答。84% が使っている・使う予定。正確さを信じる 約 33%、信じない 約 46%（強く信じる 3.1%）。一番の不満は「almost right, but not quite」（66%）、次が「Debugging AI-generated code is more time-consuming」（45.2%）。AI agents を仕事で使うのは約 31%。vibe coding をしていないが 77%（「No」72.2% と「No, emphatically」5.3%）。
  - 原文：「AI solutions that are almost right, but not quite」
  - 限界：自分で選んで答えるアンケート。
  - この学生への関係：「ほぼ正しい」コードを直す時間が一番の不満、という点が研究コードの検証の手間と重なる（私の推論）。

#### (4) AI が書いた研究コードの誤り・研究の問題・取り下げ

- **Gabrielle O'Brien, Reed Milewicz, Nasir Eisty（2026-09-18、arXiv 2609.22049）**：How Researchers Use and Verify AI Coding Assistants: Tasks and Validation Practices in Scientific Programming。https://arxiv.org/abs/2609.22049 。読んだ（要旨のみ）
  - していること・わかったこと：2025 年のアンケート（研究でコードを書く研究者、主に米国の大学）の自由記述 527 件。使う場面は data handling、visualization、debugging、数学・科学計算、統計解析。評価は形式ばらない個人のもの：半分以上は「生成したコードを走らせた」。自動テストや他人の review はまれ。経験の浅い人は自分より AI を信じ、経験のある人は逆。評価への自信は、実際にした確かめ方とは関係がなかった。
  - 原文：「Evaluation was informal and individual.」「Less experienced programmers trusted the AI more than themselves, and experienced programmers the reverse.」
  - 限界：自己申告、1 人 1 課題。著者の書いた限界は要旨になく、確かめていない。検索結果では元のアンケートは 868 人（University of Michigan）とあるが、確かめていない。
  - この学生への関係：一番近い研究。研究者の多くは「走らせて結果を見る」だけで確かめている。テストや別の方法での照合が少ない。

- **Jiaxin Cui, Rohan Alexander（University of Toronto、2026-02-15、arXiv 2602.14349）**：Same Prompt, Different Outcomes: Evaluating the Reproducibility of Data Analysis by LLMs。https://arxiv.org/abs/2602.14349 。読んだ（要旨のみ）
  - していること・わかったこと：2 つの prompt、6 つのモデル、4 つの temperature、各 10 回、計 480 回のデータ解析を走らせた。同じ設定でも解析結果に大きなばらつきがあった。検索結果の要約では、コードはほぼ常に文法的に正しいが、並べ替え・欠損値の扱い・どのレコードを含めるかなどのデータ準備で人の解析と違い、推定値がいくつかの塊に分かれる、とある（本文で確かめていない）。
  - 原文：「it should be run multiple times independently and the distribution of results considered」
  - 限界：データセットとモデル名は要旨になく、確かめていない。
  - この学生への関係：同じ指示でも結果が変わる。AI に解析を任せたら、1 回の結果で結論を出さない。

- **Beel, Kan, Baumgart（SIGIR Forum 2025、v3 2025-10-15、arXiv 2502.14297）**：Evaluating Sakana's AI Scientist: Bold Claims, Mixed Results, and a Promising Future?。https://arxiv.org/abs/2502.14297 。読んだ（要旨のみ）
  - していること・わかったこと：Sakana の AI Scientist を独立に評価。12 の実験のうち 5 つ（42%）が coding errors で失敗。1 回の改変でコードは平均 8% の文字しか増えない。原稿の引用は中央値 5 件で古い。検索結果の要約では、数値結果の hallucination を含む原稿があった、とある（確かめていない）。
  - 原文：「Our evaluation of the AI Scientist reveals critical shortcomings.」
  - 限界：1 つのシステムの評価。
  - この学生への関係：実験コードを AI に任せきりにすると、走らない・論理が間違う結果が多い、という例。

- **GPTZero（企業、2026-01-21）**：NeurIPS 2025 accepted papers の hallucinated citations の調査。https://gptzero.me/news/neurips/ 。読んだ
  - していること・わかったこと：採択論文 5,290 件のうち 4,841 件を調べ、少なくとも 100 件の存在しない引用を見つけた（論文数は本文で 51 と 53 の両方）。1 件ずつ人が確かめたという。
  - 原文：「each of the hallucinations presented here has been verified by a human expert」「These flagged citations are not automatically hallucinations」
  - 限界：GPTZero は検出ツールを売る会社。AI が原因と断定はしていない（検索結果の後続研究 arXiv 2602.05930 は 66% が完全な捏造と分類、確かめていない）。
  - この学生への関係：論文の参考文献を AI に作らせたら、1 件ずつ実物を確かめる。

- **MIT 経済学部（Acemoglu・Autor の声明、2025-05-16）**：Assuring an accurate research record。https://economics.mit.edu/news/assuring-accurate-research-record 。読んだ
  - していること・わかったこと：MIT の博士学生の未公刊論文（AI が材料科学の発見を増やすという内容）について、MIT の内部調査のあと、データの来歴・信頼性・妥当性を信頼できないと表明し、学術的な議論で使わないよう求めた。検索結果の記事では、論文は AI を使ったチームで新しい材料が 44% 多いなどと主張していた、arXiv と QJE に取り下げを求めた、とある（記事のみ、確かめていない）。
  - 原文：「we have no confidence in the provenance, reliability or validity of the data and in the veracity of the research.」
  - 限界：AI ツールが誤りを生んだ例ではない。「AI の科学への効果」を主張した論文の信頼性の問題。
  - この学生への関係：AI の効果を示す有名な研究でも、データが疑われて撤回されることがある。数を引用する前に元を確かめる。

#### (5) 研究者の AI 利用の調査

- **Wiley（出版社、2025-10-07）**：ExplanAItions 第 2 回。https://newsroom.wiley.com/press-releases/press-release-details/2025/AI-Adoption-Jumps-to-84-Among-Researchers-as-Expectations-Undergo-Significant-Reality-Check/default.aspx 。読んだ（プレスリリースのみ）
  - していること・わかったこと：2025-08 に研究者 2,430 人。AI の利用は 2024 年の 57% から 84%。研究・出版の作業での利用は 45% から 62%。inaccuracies / hallucinations への懸念は 51% から 64%。AI が人より上と思う用途は、半分以上から 3 分の 1 未満に減った。
  - 原文：「researchers are significantly scaling back their expectations of what AI can currently do」
  - 限界：出版社の調査。方法の詳細は報告書本体にあり、確かめていない。第 1 回（2025-02、4,946 人、コンピュータ科学者の利用が多い）は Nature の記事 https://www.nature.com/articles/d41586-025-00343-5 で報じられたが、Nature は開けなかった（検索結果だけ）。

- **Lyttelton, Massenkoff, Wilmers（Anthropic、2026-05-27）**：Coding agents in the social sciences。https://www.anthropic.com/research/coding-agents-social-sciences 。読んだ
  - していること・わかったこと：量的社会科学者 1,260 人のメール調査（2026-02〜03）。約 30% が博士学生。81% が生成 AI を研究に使ったことがある。coding agents を日常的に使うのは 20%（その 86% が Claude Code、31% が Codex）。agent 利用者の 97% がコード生成に使う。agent 利用者はプロジェクトや working paper が多いが、投稿数や再投稿の速さに明らかな差はない。
  - 原文：「Only 20% of respondents use coding agents.」「Differences should not be interpreted as causal.」
  - 限界（著者）：Claude Max を配る研究で募集したので AI に関心のある人に偏る。自己申告。質は測っていない。Anthropic 自身の調査。
  - この学生への関係：分野は違うが、博士学生を含む研究者の Claude Code 利用の数少ない数。

#### 共通して言われていること

出典の言うこと：
- 自己評価と実測がずれる。METR 2025（速くなったと思ったが 19% 遅い）、Perry et al.（安全だと思うが安全でない）、Lehmann et al.（学んだと感じる量が実際より大きい、検索結果の要約）、METR 2026 アンケート（著者自身が自己申告は現実に基づくとは限らないと書く）。
- 使い方で結果が分かれる。Shen & Tamkin と Lehmann et al. の両方で、全部を任せる・解答を求める使い方は学習が少なく、説明や概念を尋ねる使い方は学習が残る。
- 書くコードの量は増えるが、その先は増え方が小さい。He et al.（速さは 2 か月で消え、warnings と complexity は残る）、Demirer et al.（commits 240% が release で 30%）。
- 経験者は agent に任せきりにせず、plan・小さい手順・review で制御している（Huang et al.、Watanabe et al. の手直し 45.1%）。
- 研究者の利用は急に増え、同時に誤りへの懸念も増えている（Wiley：84%、懸念 64%）。研究者の確かめ方は「走らせる」が中心で、テストや他人の review は少ない（O'Brien et al.）。

私の推論：上の 5 つは、研究コードでは「動いたから正しい」とせず、別の方法で結果を照合する手間を最初から見込むべき、という方向でそろっている。

#### 意見が分かれていること

- 生産性の大きさと向き：Cui et al.（企業の RCT、4,867 人、+26%、経験の浅い人ほど伸びる）と METR 2025（経験者 16 人、−19%）は逆。違いは経験、コードベースへのなじみ、測る量（件数か時間か）、道具の世代。METR 2026 は新しい道具では速くなった可能性が高いと言うが、数は出せていない。
- 新しい道具（agent）での効果：Demirer et al. は agent で commits が大きく増えると言い、METR は 2026 年の参加者でも測定が崩れたと言う。agent での RCT の確かな数はまだない。
- 学習への害：Shen & Tamkin は有意な低下、Lehmann et al. は全体では効果なし。どちらも使い方による差を報告しているので、矛盾ではなく測った条件の違いかもしれない（私の推論、確かめていない）。
- 「AI のコードの品質」：Veracode は security が良くならないと言い、Watanabe et al. は 83.8% が merge されると言う。測っているもの（脆弱性か、受け入れか）が違う。

#### 見つからなかったこと・確かめていないこと

- 博士学生・修士学生だけを対象にした Claude Code（agent）の実証研究は見つからなかった。近いのは METR 2026 アンケート（academics and PhD students 37%）と Anthropic の社会科学者調査（約 30% が博士学生）だけ。
- 機械学習・強化学習の研究コードで、AI が書いたコードの誤りの率を測った研究は見つからなかった。O'Brien et al.、Cui & Alexander、Beel et al. は一般の科学計算・データ解析・自動研究システムについて。
- Claude Code や agent を使ったときの学習への影響の RCT はない。Shen & Tamkin 自身が agent は調べていないと書いている（Anthropic の社会科学者調査の続きが Claude Code の無作為割り当てを予定している、と記事にある）。
- 確かめていない数：DORA 2025 の数（PDF を開けなかった）、Nature の 2025 年の調査（開けなかった）、Perry et al. の参加人数、Lehmann et al. の標本の大きさと効果量、Veracode の課題数と方法、Cui & Alexander のデータとモデル名、Watanabe et al. の人の PR の率と採録先、Cui et al. の Management Science 掲載、He et al. の complexity の 41.6% と 25% の食い違い、MIT の件の arXiv での現状。
- 査読前のもの：Demirer et al.（NBER）、O'Brien et al.、Cui & Alexander、Shen & Tamkin、Huang et al. は arXiv や working paper で、査読済みかは確かめていない。He et al.（MSR '26）、Perry et al.（CCS '23）、Beel et al.（SIGIR Forum）は掲載先が書かれている。
- 企業の報告（Veracode、GPTZero、Stack Overflow、Wiley、Anthropic、METR）は、自分の製品や立場に関係する。数は書いてある通りに写したが、独立に確かめていない。

### 学会・大学の規則と開示

調べた日：2026-11-16。ページは WebFetch で開いた。WebFetch は小さなモデルがページを要約して返す。「原文」は WebFetch が原文として返した文で、1 文字ずつの照合はしていない（確かめていない）。論文に引くときは、ページを自分で開いて確かめる必要がある。

#### 出典

#### 情報処理学会（GPW・ゲーム情報学研究会の親の学会）

- **学会**（情報処理学会、2026-07-03 公開）：FAQ「会誌の記事や論文執筆時に生成AI を利用してもよいですか？」。https://www.ipsj.or.jp/faq/copyright_39.html 。読んだ
  - していること・わかったこと：生成 AI の利用を推奨する。責任はすべて著者。生成 AI は著者・著作権者にしない。開示が必要かは、このページには書かれていない。会誌・論文誌・行事ごとの規定が優先する。
  - 原文：「記事・論文の内容の正確性・引用の適切性・著作権侵害の有無等についての責任は、AI の利用如何にかかわらず、すべて著者に帰属します。」「生成AI は責任を負う主体とはなり得ないため、情報処理学会においては、生成AI を著者や著作権者として扱いません。」
  - この学生への関係：GPW の論文も情報処理学会の催しなので、この考え方が土台になると思われる（推測。GPW の規定は見つけていない）。

- **学会**（情報処理学会、日付の記載なし）：FAQ「［全国大会］生成AIを使用して論文を作成してもいいですか？」。https://www.ipsj.or.jp/faq/taikai_38.html 。読んだ
  - していること・わかったこと：禁止しない。責任は著者。「プログラム」の設計・実装・挙動を自分の言葉で説明できることを例に挙げている。
  - 原文：「生成AIの使用は禁止しません。但し、いかなる場合においても、生成AIを利用した結果についての責任は著者が負うものとします。」「（*例えば、研究の着想、研究計画、制作したプログラムの目的・設計・実装・挙動などの独自性について、その内容について十分な理解を持って自分の言葉で説明できることなど）」
  - この学生への関係：Claude Code が書いたコードでも、学生が設計・実装・挙動を説明できることが求められる。国内の規則でコードにはっきり触れた数少ない例。

- **学会**（情報処理学会論文誌 特集号の募集、2026-07-07 掲載、締切 2026-11-27）：「AIによって変わる社会基盤を支えるコンピュータセキュリティ技術」特集 論文募集。https://www.ipsj.or.jp/journal/cfp/27-M.html 。読んだ
  - していること・わかったこと：利用は一律に禁止しない。利用した場合は謝辞などに書くことを「推奨」。書いたかどうかで採否を決めない。
  - 原文：「生成AIを利用した場合には、その内容および利用方法を謝辞（Acknowledgements）等に記載することを推奨します。」「なお、生成AIの利用に関する記載の有無自体をもって採否を判断することはありません。」
  - この学生への関係：情報処理学会の中で、開示の場所（謝辞）と強さ（推奨）を書いた例。ほかの特集・研究会にも同じ文があるかは確かめていない。

- **学会**（情報処理学会論文誌ジャーナル、更新日は確かめていない）：原稿執筆案内。https://www.ipsj.or.jp/journal/submit/ronbun_j_prms.html 。読んだ
  - していること・わかったこと：生成 AI の記述はない。プログラムの公開（再現性）の記述もない。
  - この学生への関係：論文誌に出すときは、上の FAQ と特集ごとの募集要項を見ることになる。

#### 国際会議

- **学会**（NeurIPS 2025）：LLM Policy。https://neurips.cc/Conferences/2025/LLM 。読んだ
  - していること・わかったこと：方法の実装に LLM を使い、それが重要・独自・標準的でない部分なら、実験設定の節に書く。編集目的のプログラミングの手助けは書かなくてよい。責任は著者。
  - 原文：「The use of LLMs in implementing the method should be described in the experimental setup section」「The use of spell checkers and grammar suggestions, programming aid for editing purposes does not need to be documented.」「authors are responsible for the entire content of the paper, including all text, figures, and references」
  - この学生への関係：Claude Code でコードを書いただけなら、NeurIPS の基準では開示は必須でない。LLM を方法の一部にしたときだけ必須。

- **学会**（NeurIPS、年は確かめていない）：Paper Checklist Guidelines。https://neurips.cc/public/guides/PaperChecklist 。読んだ
  - していること・わかったこと：項目 5 でコード・データ・再現の手順を出したかを問う。コードがないだけで不採択にはしない（コードが貢献の中心なら別）。項目 16 が LLM の利用の申告。
  - 原文：「Did you include the code, data, and instructions needed to reproduce the main experimental results」「Papers cannot be rejected simply for not including code, unless this is central to the contribution」「we do require all submissions to provide some reasonable avenue for reproducibility」
  - この学生への関係：再現性は AI の利用と別の項目で問われる。AI が書いたコードでも、公開と手順の説明が求められる。

- **学会**（NeurIPS 2026 Evaluations & Datasets Track）：Reviewing Guidelines。https://neurips.cc/Conferences/2026/EvaluationsDatasetsReviewerGuidelines 。読んだ
  - していること・わかったこと：「basic coding assistance」は開示不要とはっきり書いている。再利用できる実行可能な成果物ではコードの公開が必須。
  - 原文：「Routine uses such as spell checking, grammar editing, or basic coding assistance do not need to be disclosed.」「code release is mandatory at the time of submission」
  - この学生への関係：「basic coding assistance」と agentic coding（Claude Code がコードの大部分を書く）の境目は書かれていない（確かめていない）。

- **学会**（NeurIPS 2026 Position Paper Track、2026-06-02）：AI-Generated Papers in the NeurIPS 2026 Position Paper Track。https://blog.neurips.cc/2026/06/02/ai-generated-papers-in-the-neurips-2026-position-paper-track/ 。読んだ
  - していること・わかったこと：論文本文は人が書くこと。研究の中での AI の利用は認める。AI 検出器（Pangram）で 178 本を desk reject した。コードの扱いには触れていない。
  - 原文：「the final paper must itself be substantially written by human authors」「While AI tools may be used in the research that leads to the final paper」
  - この学生への関係：文章とコードで扱いを分ける会議が出てきた例。

- **学会**（ICML 2025）：Call for Papers。https://icml.cc/Conferences/2025/CallForPapers 。読んだ
  - していること・わかったこと：執筆と研究に生成 AI を使ってよい。責任は著者。方法の中での目立つ使い方は説明を「勧める」。
  - 原文：「Authors are allowed to use generative AI tools such as Large Language Models (LLMs) to assist in writing or research.」「We encourage authors to explain any notable ways in which these tools were used in their research methodology.」
  - この学生への関係：ICML 2026 の著者向けの文は、開いたページ（Intro-LLM-Policy、査読者向け）では見つからなかった（確かめていない）。

- **学会**（ICLR 2027、日付の記載なし）：AI Policy for Authors。https://iclr.cc/Conferences/2027/AIPolicyForAuthors 。読んだ
  - していること・わかったこと：論文の中に AI 利用の開示の節を必須にした（ページ数に数えない）。「implement methods」は開示が必須、「create or edit software code」は推奨。テンプレートに「LLM が書いたコードはテストで確かめた」という例がある。
  - 原文：必須の一覧に「design or provide feedback on research methodology or experiments, implement methods」、推奨の一覧に「suggest experimental parameters, create or edit software code」。テンプレートの末尾「We take responsibility for the final content of this work」「including text, claims or artifacts produced with the aid of generative AI」
  - この学生への関係：見つけた中で、コードについて一番細かい規則。「方法の実装」と「コードの作成・編集」を分けている。Claude Code に方法そのものを実装させたなら、ICLR では必須側に入ると読める（推測）。

- **学会**（IJCAI 2025）：Call for papers (Main Track)。https://2025.ijcai.org/?p=1068 。読んだ
  - していること・わかったこと：LLM は著者にならない。執筆に LLM を使ったら、全内容（剽窃と正しさの確認を含む）に責任を持つ。再現性のガイドラインとチェックリストに従う。コードは匿名化する。
  - 原文：「If authors use an LLM in any part of the paper-writing process they assume full responsibility for all content」「Authors must follow the reproducibility guidelines」
  - この学生への関係：コードを匿名化するとき、Claude Code が書いたファイル中のパスや名前にも注意が要る（推測）。

- **学会**（AAAI-25）：Policies for AAAI-25 Authors。https://aaai.org/conference/aaai-25/policies-for-aaai-25-authors/ 。読んだ
  - していること・わかったこと：LLM が生成した文章を含む論文は禁止（実験の分析の一部として示す場合を除く）。自分で書いた文の編集・推敲は可。コードについての記述はない。AAAI-26 の文は開いていない（確かめていない）。
  - 原文：「Papers that include text generated from a large-scale language model (LLM) such as ChatGPT are prohibited」「this policy does not prohibit authors from using LLMs for editing or polishing author-written text.」
  - この学生への関係：文章には厳しいがコードには触れていない例。

- **学会**（ACL 2023、2023-01-10 更新）：ACL 2023 Policy on AI Writing Assistance。https://2023.aclweb.org/blog/ACL-2023-policy/ 。読んだ
  - していること・わかったこと：コードの手助け（Copilot など）は使ったことと範囲を書く。コードの手助けを使っても、方法と結果の正しさを確かめる義務は残る。README に書くことを挙げている。
  - 原文：「For now, we ask the authors to acknowledge the use of such systems and the scope thereof」「The use of code assistance does not obviate the requirements of authors to ensure the correctness」
  - この学生への関係：AI が書いたコードの正しさの責任を、はっきり著者に置いた最初期の文。2023 年で古いが、この話題の元になった規則。

- **学会**（ACL Rolling Review、日付は確かめていない）：Responsible NLP Research checklist。https://aclrollingreview.org/responsibleNLPresearch 。読んだ。あわせて https://aclrollingreview.org/responsible-nlp-checklist-appendices は検索結果だけ
  - していること・わかったこと：項目 E1 で AI assistant の利用を書いたかを問う。検索結果によれば EMNLP 2025 からチェックリストが論文の付録として公開される（このページは開いていない）。
  - 原文：「If you used any AI assistants, did you include information about your use?」
  - この学生への関係：開示が論文と一緒に公開されるので、ほかの研究者の開示文の実例を大量に読める。

#### 学会（出版社）・プレプリント

- **学会**（ACM、日付は確かめていない）：Frequently Asked Questions（Authorship）。https://www.acm.org/publications/policies/frequently-asked-questions 。検索結果だけ（403 で開けなかった）
  - していること・わかったこと（検索結果の要約から）：生成 AI はどんな条件でも著者にならない。利用は可。計算機が生成した部分も含めて著者が責任を持つ。綴り・文法の修正だけなら開示不要。BioRender の要約サイトは「code」も含めて謝辞で開示と書いているが、ACM の原文では確かめていない。2026-05-14 に改訂されたという話も確かめていない。
  - 原文（検索結果の中の引用）：「generative AI software tools cannot be listed as authors on ACM Works under any conditions」
  - この学生への関係：ACM の会議（例：CHI、ICSE）に出すなら、ページを直接開いて確かめる必要がある。

- **学会**（IEEE、日付の記載なし）：Author Guidelines for Artificial Intelligence (AI)-Generated Text。https://open.ieee.org/author-guidelines-for-artificial-intelligence-ai-generated-text/ 。読んだ
  - していること・わかったこと：AI が生成した内容（文章・図・画像・コード）は謝辞で開示する。AI の名前、使った節、どの程度使ったかを書く。編集・文法の改善は対象外だが開示を勧める。
  - 原文：「(including but not limited to text, figures, images, and code)」「a brief explanation regarding the level at which the AI system was used」
  - この学生への関係：IEEE はコードも開示の対象に入れている。IEEE CoG（ゲームの会議）に出すならこれが関係する（CoG 独自の規則は調べていない）。

- **出版社**（Springer Nature、日付は確かめていない）：AI guidance for our researchers and communities。https://group.springernature.com/gp/group/ai/ai-guidance-for-our-researchers-and-communities 。読んだ
  - していること・わかったこと：LLM は著者にならない。利用は Methods の節（またはそれに当たる場所）に書く。コードには触れていない。copy editing の扱いはこのページでは「AI guidance に沿って申告」とあり、検索結果の要約サイトには「申告不要」とあって食い違う（確かめていない）。
  - 原文：「Large Language Models (LLMs) do not meet Springer Nature’s authorship criteria」「Their use must be documented in the manuscript’s Methods section (or equivalent).」
  - この学生への関係：ACG や Computers and Games（LNCS）が Springer から出るなら関係する（これらの会議の現在の出版社は確かめていない）。

- **プレプリントサーバー**（arXiv、日付は確かめていない）：Moderation（Policy for authors' use of generative AI language tools）。https://info.arxiv.org/help/moderation/index.html 。読んだ
  - していること・わかったこと：text-to-text の生成 AI は報告すべき道具に入る。中身の責任は、どう生成されたかに関係なく著者。AI は著者にしない。
  - 原文：「they each individually take full responsibility for all its contents, irrespective of how the contents were generated」
  - この学生への関係：arXiv に出すときの土台の規則。

- **報道**（GIGAZINE、2026-05-15）：arXiv の CS 部門の責任者 Thomas G. Dietterich の発表（X への投稿、2026-05-14）の記事。https://gigazine.net/gsc_news/en/20260515-arxiv-ai-paper-banned 。読んだ（Dietterich の投稿そのものは開いていない）
  - していること・わかったこと：確かめずに残した LLM の誤り（存在しない参考文献、「Here is a 200-word summary」のような LLM の文の残り）があれば 1 年の投稿禁止。AI の利用そのものは禁止しない。記事の時点では arXiv の公式の規則ページは未更新。
  - 原文：記事が引く例「Here is a 200-word summary」
  - この学生への関係：AI の利用より「確かめなかったこと」が罰の対象になっている。

#### 大学

- **大学**（東京大学、2023-05-26、ver. 1.0）：東京大学の学生の皆さんへ：AIツールの授業における利用について。https://utelecon.adm.u-tokyo.ac.jp/docs/ai-tools-in-classes-students/ 。読んだ
  - していること・わかったこと：一律に禁止しない。授業ごとに担当教員が決める。使ったツールを書くよう求められることがある。プログラミングについての記述はない。研究・論文向けの全学の規則は見つからなかった。
  - 原文：「AIツールを用いて作成したものについては、どのツールを用いたかを記載することが求められることがあります。」「生成結果を鵜吞みにするのではなく、自ら必ず吟味したうえ、適宜修正するなどした上で活用する必要があります。」
  - この学生への関係：授業向けで、研究のコードの規則ではない。2023 年の暫定版のまま。

- **大学**（東京農工大学、2026-02-02）：国立大学法人東京農工大学における生成 AI 利活用ガイドライン。https://www.tuat.ac.jp/documents/tuat/NEWS/info/AIGuideline_20260202.pdf 。読んだ（PDF から文字を取り出して読んだ）
  - していること・わかったこと：研究活動の節に「プログラム作成等で用いる場合」がある。提案されたコードを理解できること、ライブラリが汚染されていないことを確かめてから使う。未公開の研究データやアイデアは、エンタープライズ保護がなければ入力しない。論文は投稿先の学会の指示に従う。
  - 原文：「プログラム作成等で用いる場合は、生成 AI から提案された記述例が理解できること、ライブラリ等が汚染されていないことを確認した上で使用してください。」「新規性のある未公開の研究データやアイデアは入力すべきではありません。」
  - この学生への関係：大学の規則で、研究のコードにはっきり触れた例。未公開のデータ・アイデアを Claude Code に渡すことの扱いは、所属大学の契約（エンタープライズ保護に当たるか）によって変わる（この学生の大学の規則は調べていない。指示どおり）。

#### 研究論文・ガイド

- **研究論文**（Nahar, Lee, Guillen, Lee、arXiv v4 2025-03-12）：Generative AI Policies under the Microscope: How CS Conferences Are Navigating the New Frontier in Scholarly Writing。https://arxiv.org/html/2410.11977v4 。読んだ
  - していること・わかったこと：CS の会議 64 個の規則を調べた。著者向けの規則がある会議は 1 年目 28.1%、2 年目 48.4%。著者向けは多くが「moderately to very lenient」。AI の会議が一番寛容。違反の罰を決めた規則はなかった。コードの記述について書いた規則は一部。
  - 原文：「Both authors and reviewers should disclose Gen-AI use transparently and take full responsibility.」
  - この学生への関係：会議ごとの規則のばらつきを数で示した論文。

- **研究論文**（Mohapatra, Pruthi、arXiv 2026-08-24 v1、08-25 v2）：Expectations and Practices around AI Disclosure in CS Research。https://arxiv.org/html/2608.23271v2 。読んだ
  - していること・わかったこと：CS 研究者 109 人の調査と、EMNLP 2025・ICLR 2026 の開示文 13,867 件の分析。開示文で「Creating or editing software code」は ICLR 2026 で 16.1%、EMNLP 2025 で 23.3%。参加者はコードの手助けの開示を「less necessary」と見る（平均 2.96）。著者自身の開示文が Claude Code の開示の実例になっている。
  - 原文（著者の開示文）：「we used generative AI tools (Claude Code) to create and edit software code」「All generated code was manually verified for correctness.」
  - この学生への関係：Claude Code の利用をどう書くかの短い実例。数値は WebFetch の返した値で、ページの表示に数字が二重になる崩れがあった。論文に引くなら PDF で確かめる必要がある。

- **研究論文**（Suwannik、arXiv 2026-04-11）：Applying an Agentic Coding Tool for Improving Published Algorithm Implementations。https://arxiv.org/abs/2604.13109 。読んだ（要旨だけ）
  - していること・わかったこと：Claude Code で公開済みのアルゴリズムの実装を改善した。要旨は、実験の妥当性の確認など人が欠かせない部分を分析したと言う。検索結果の要約では、実験のスクリプトはすべて Claude Code が書いたと本文で開示している（本文は確かめていない）。
  - 原文：「Claude Code reported that all eleven experiments yielded improvements」
  - この学生への関係：Claude Code の報告をそのまま結果にしない、という点の例（著者の主張の確認は確かめていない）。

- **大学のサービス**（University of Göttingen の AI Usage Cards、2026-08-31 更新）：AI disclosure for computer science research papers。https://aicards.uni-goettingen.de/ai-disclosure-for-computer-science-research-papers/ 。読んだ
  - していること・わかったこと：コードの開示には、道具・作業・影響したファイルやモジュール・確かめ方を書く。結果に関わるコードは methods の節に書く。実験・ベースライン・データの整形・評価・学習に触れたら開示する。例文あり（Copilot で前処理モジュールのテストと補助関数を書き、出力を見本と照らした、など）。
  - 原文：「A useful code disclosure names the tool, the task, the files or modules affected, and your verification steps.」「Put method relevant AI use in the methods section.」
  - この学生への関係：規則ではなくガイド。開示文を書くときの項目の目安になる。

#### 共通して言われていること

- AI は著者にしない（情報処理学会、ACM、IJCAI、AAAI、arXiv、Springer Nature、NeurIPS）。
- 中身の責任は、AI を使ったかに関係なく著者にある。ほぼすべての出典がこう書く。ACL 2023 と情報処理学会の全国大会 FAQ は、コードについてもこれを言う。
- 綴り・文法の修正だけなら開示しなくてよい（NeurIPS、ACM〔検索結果〕、IEEE〔推奨はする〕、ACL）。
- AI の利用が方法の一部なら、方法・実験設定の節に書く（NeurIPS、IJCAI、Springer Nature、ICLR、Göttingen のガイド）。
- 確かめなかった AI の出力（存在しない参考文献など）は違反・罰の対象になる（NeurIPS 2025、arXiv 2026、ICLR）。
- 再現性（コード・データ・手順の公開）は、AI の利用とは別の項目で求められる（NeurIPS チェックリスト、NeurIPS 2026 E&D、IJCAI）。

#### 意見が分かれていること

- **コードの手助けを開示するか**：
  - 不要：NeurIPS 2025（「programming aid for editing purposes」）、NeurIPS 2026 E&D（「basic coding assistance」）。
  - 推奨：ICLR 2027（「create or edit software code」）、情報処理学会の特集号（謝辞に記載を推奨）。
  - 必要：IEEE（コードを含む AI 生成の内容は謝辞で開示）、ACL 2023（使ったことと範囲を書く）。
  - 研究者の調査では、コードの開示は「less necessary」と見られている（Mohapatra, Pruthi）。
- **開示の場所**：謝辞（IEEE、情報処理学会の特集号、ACM〔検索結果〕）、Methods・実験設定（Springer Nature、NeurIPS、Göttingen のガイド）、専用の必須の節（ICLR）、チェックリスト（ACL の E1、NeurIPS の項目 16）。
- **「方法の実装」と「コードを書く手助け」の境目**：ICLR は前者を必須、後者を推奨と分ける。NeurIPS は「重要・独自・標準的でない」かで分ける。Claude Code がコードの大部分を書く agentic coding がどちらに入るかを直接書いた規則は見つからなかった。
- **文章の扱い**：AAAI-25 と NeurIPS 2026 Position Paper Track は LLM の書いた本文に厳しい。情報処理学会は利用を「推奨」する。コードには、どちらも触れていない。

#### 見つからなかったこと・確かめていないこと

- GPW と情報処理学会ゲーム情報学研究会に独自の生成 AI の規定は、検索で見つからなかった。ipsj.or.jp の研究会のページは開いていない。
- ACM の原文（403 で開けなかった）。コードを謝辞で開示するという文と、2026-05 の改訂は確かめていない。
- AAAI-26 と ICML 2026 の著者向けの文は開いていない。NeurIPS 2026 本会議の LLM Policy のページは 404 だった。
- 東京大学の研究・論文向けの全学の規則は見つからなかった。京都大学・東京科学大学の規則は検索で見つからなかった。文部科学省・JSPS の研究公正の文書で生成 AI に触れたものは調べていない。
- AI が書いたコードとログの公開（例：Claude Code の会話ログやコミットの Co-Authored-By）を求める会議の規則は見つからなかった。NeurIPS 2026 Position Paper Track の「audit trail」は文章の版の履歴のことで、コードのログではない。
- 原文の引用は WebFetch が返したもので、1 文字ずつの照合はしていない。Mohapatra, Pruthi の数値（16.1%、23.3%、2.96）も PDF では確かめていない。
- Suwannik の論文は要旨だけ読んだ。本文の開示文は確かめていない。


## 本人が決めたこと（2026-11-16）

- commit と push は本人がする。Claude Code は git commit・git push を実行しない（memory の user-pushes-commits.md にそろえ、食い違っていた no-commit-without-asking.md を消した。short-commit-messages.md の Co-Authored-By の行も「付けない」に直した）。
- panel は止めない。
- 投了の不具合は先生に伝える。報告は mdfolder/meeting_2026-11-16.md に書いた。
- 下の「足りないこと」4 つを、本人が行う。
- ほかの「決めること」には、あとで答える。

### 足りないこと（これから行う）

- [ ] 1. 本人が何も見ずに説明する段階を作る。mdfolder/code_reading_plan.md:51-57 の「読んだ日」の表は、5 章とも空である。
- [ ] 2. 確かめのスクリプト（scripts/shogi_env_check.py、scripts/dobutsu_env_check.py）を、決まった時点（環境・学習の正解・損失に関わるファイルを変えたあと、学習を始める前）で実行する仕組みを作る。今の hooks は Notification だけである。
- [ ] 3. 発表に出す数字を作ったスクリプトを残す。図 5 のベースラインを 11-11 に数えたスクリプトは見つからない。投了の不具合の数（mdfolder/meeting_2026-11-16.md のコマンド 1 と 2）も、スクリプトのファイルとしては残っていない。memory の「確かめに新しいファイルを作らない」が原因の一部である。
- [ ] 4. panel と、離れている間の loop に、回数と token の上限を決める。今は「2 回続けて新しい指摘がないとき」に止める（memory の away-task-loops.md）。

# Contract: tags フィルタ統合 + news_sites/articles を collect に追加

## Inputs
- `sources/news_sites.yaml`: 各 site エントリに `tags: [tech, ai, ...]` フィールドを追加
- `sources/articles.yaml`: 各 feed エントリに `tags: [tech, ai, ...]` フィールドを追加
- `radar collect` コマンドに `--include-tags` オプション（デフォルト: `tech,dev,ai`）

## Outputs
- `radar collect` 実行時に ZennCollector + NewsCrosscheckCollector も実行される
- include_tags に一致するタグを持つソースのみが収集対象となる
- 既存の JSON エクスポート形式は変わらない（後方互換）

## Invariants
- エラー時: 非0終了 + stderr にメッセージ。stdout にゴミを出さない
- 後方互換: タグなし（既存ソース）はデフォルトで include 扱い（tags フィールドなし = 全タグにマッチ）
- collect の既存動作（RSS/GitHub 収集）は変わらない
- ZennCollector / NewsCrosscheckCollector のエラーは警告に留め、他の収集は継続する

## Tags 設計
各ソースの tags（yaml に追記）:

### news_sites.yaml
| サイト | tags |
|--------|------|
| Gigazine | [product, news] |
| ITmedia AI+ | [tech, ai] |
| ITmedia News | [tech, news] |
| Publickey | [tech, dev] |
| クラウドWatch | [tech, cloud] |
| HackerNews | [tech, dev, community] |
| Ars Technica | [tech, dev] |
| The Verge | [product, news] |

### articles.yaml（Zenn feeds）
| トピック | tags |
|---------|------|
| ai | [tech, ai] |
| devops | [tech, dev] |
| automation | [tech, dev] |
| mcp | [tech, dev, ai] |
| claudecode | [tech, dev, ai] |

## フィルタロジック
```python
def matches_include_tags(source_tags: list[str], include_tags: list[str]) -> bool:
    if not source_tags:  # tags 未定義 = 後方互換（常にtrue）
        return True
    return bool(set(source_tags) & set(include_tags))
```

## 実装対象ファイル
1. `sources/news_sites.yaml` — tags フィールド追記
2. `sources/articles.yaml` — tags フィールド追記
3. `collectors/news_crosscheck.py` — `_load_config()` でタグフィルタを適用
4. `collectors/zenn_collector.py` — `_load_config()` でタグフィルタを適用
5. `collectors/cli.py` — `collect` コマンドに ZennCollector + NewsCrosscheckCollector 追加、`--include-tags` オプション追加

## Tests（Given/When/Then）

### Test 1: include_tags デフォルトで product ソースが除外される
- Given: news_sites.yaml に tags=[product,news] の Gigazine が定義されている
- When: `radar collect`（デフォルト --include-tags tech,dev,ai）を実行
- Then: 収集結果に Gigazine のエントリが含まれない

### Test 2: tech タグのソースが収集される
- Given: news_sites.yaml に tags=[tech,dev] の Publickey が定義されている
- When: `radar collect --include-tags tech,dev,ai` を実行
- Then: 収集結果に Publickey のエントリが含まれる（接続可能な場合）

### Test 3: tags 未定義ソースは後方互換で常に収集される
- Given: providers.yaml の既存ソース（tags フィールドなし）
- When: `radar collect --include-tags tech,dev,ai` を実行
- Then: 既存ソースは収集対象のまま（除外されない）

### Test 4: --include-tags オプションで上書き可能
- Given: news_sites.yaml に tags=[product] の The Verge がある
- When: `radar collect --include-tags tech,dev,ai,product` を実行
- Then: The Verge も収集対象になる

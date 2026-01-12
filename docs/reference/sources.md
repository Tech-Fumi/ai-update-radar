# 監視対象（Sources）

監視対象の定義と仕様。

## 構成

```
sources/
├── openai.yaml
├── anthropic.yaml
├── google.yaml
└── ...
```

## フォーマット

```yaml
name: provider-name
url: https://...
check_interval: daily
type: api_changelog | blog | release_notes
```

## 現在の監視対象

| Provider | Type | Interval |
|----------|------|----------|
| OpenAI | API Changelog | Daily |
| Anthropic | Release Notes | Daily |
| Google | Blog | Daily |

# Sources

This directory contains configuration files for various AI update sources.

## Purpose

Define and configure the sources from which we collect AI update information.

## Planned Source Types

### Official Sources
- **Provider Blogs**: OpenAI, Anthropic, Google AI, etc.
- **API Changelog**: Direct API versioning and update feeds
- **Documentation Sites**: Changes to official documentation
- **Release Notes**: GitHub releases and version tags

### Community Sources
- **Reddit**: r/MachineLearning, r/OpenAI, r/LocalLLaMA
- **Hacker News**: AI-related discussions
- **Twitter/X**: Official accounts and key researchers
- **Discord Servers**: Community announcements

### Aggregators
- **RSS Feeds**: Curated AI news feeds
- **Newsletter Archives**: Import AI, The Batch, etc.
- **Research Trackers**: Papers with Code, arXiv

## Configuration Format (Planned)

```yaml
source:
  name: "OpenAI Blog"
  type: "rss"
  url: "https://openai.com/blog/rss"
  priority: "high"
  filters:
    - "capability"
    - "pricing"
    - "constraints"
```

## Current Status

🚧 **Not yet implemented** - Placeholder directory for future development

## Next Steps

1. Define standard source configuration schema
2. Create source registry/catalog
3. Implement source validation logic
4. Add authentication mechanisms for protected sources

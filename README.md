# AI Update Radar

An operational repository for detecting, evaluating, and experimenting with substantial AI updates.

## Philosophy

This system focuses exclusively on **meaningful changes** that impact real-world AI usage:

### What We Track

1. **Capability Changes** 🚀
   - New features or abilities (e.g., multimodal support, longer context windows)
   - Improved performance on specific tasks (e.g., better code generation, reasoning)
   - Changes in output quality or reliability
   - Removal of previous limitations

2. **Constraint Removals** 🔓
   - Lifted usage restrictions (e.g., rate limits, content policies)
   - Expanded access to previously restricted features
   - Increased quotas or capacity
   - Removed technical limitations

3. **Pricing Shifts** 💰
   - Price increases or decreases
   - Changes in pricing models (e.g., per-token to subscription)
   - New pricing tiers or options
   - Cost optimizations or discounts

### What We Ignore

- Minor UI/UX changes that don't affect API or capabilities
- Internal refactoring without user-visible impact
- Marketing announcements without technical substance
- Speculative or unverified claims

### Why This Matters

AI systems evolve rapidly, and staying informed about **substantive changes** is critical for:
- **Decision making**: Choosing the right model for specific use cases
- **Cost optimization**: Adapting to pricing changes proactively
- **Capability planning**: Leveraging new features as they become available
- **Risk management**: Understanding when constraints change

## Repository Structure

```
ai-update-radar/
├── sources/          # Configuration for update sources (blogs, APIs, RSS feeds)
├── collectors/       # Scripts to fetch and parse updates from various sources
├── evaluators/       # Logic to classify and score updates by importance
├── experiments/      # Validation experiments to verify claimed changes
└── weekly_reports/   # Automated and manual weekly summaries
```

## Workflow

1. **Collection**: Automated collectors fetch updates from configured sources
2. **Evaluation**: Evaluators filter for capability/constraint/pricing changes
3. **Experimentation**: Critical changes are validated through controlled tests
4. **Reporting**: Weekly reports summarize verified, impactful updates

## Getting Started

This repository is currently in the **structure and documentation** phase. Full implementation is planned for future development.

### Prerequisites

- Python 3.8+
- Basic understanding of AI model capabilities and pricing

### Current Status

📋 **Phase**: Repository structure and documentation  
🚧 **Implementation**: Not yet started  
📅 **Next Steps**: Implement collectors and evaluators

## Contributing

Contributions are welcome! Please focus on:
- Adding new data sources for AI updates
- Improving evaluation criteria for what constitutes a "meaningful" change
- Creating experiments to validate claimed improvements

## License

[To be determined]

---

**Note**: This project prioritizes **signal over noise**. We aim to track only the updates that truly matter for AI practitioners and decision-makers.

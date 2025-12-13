# Evaluators

This directory contains logic for analyzing, classifying, and scoring collected updates.

## Purpose

Filter and rank updates based on their significance, focusing on capability changes, constraint removals, and pricing shifts.

## Evaluation Criteria

### Capability Changes
- **Impact Score**: How significantly does this change user capabilities?
- **Scope**: How many use cases are affected?
- **Verifiability**: Can this change be experimentally validated?

### Constraint Removals
- **Restriction Type**: Rate limits, content policies, feature access
- **Impact**: How many users/use cases are affected?
- **Documentation**: Is the change officially documented?

### Pricing Shifts
- **Magnitude**: Percentage change in cost
- **Direction**: Increase, decrease, or restructuring
- **Affected Services**: Which models/APIs are impacted?
- **Effective Date**: When does the change take effect?

## Classification System (Planned)

```python
classification = {
    "type": "capability" | "constraint" | "pricing",
    "category": "multimodal" | "context" | "speed" | "quality" | ...,
    "severity": "critical" | "major" | "minor",
    "confidence": 0.0 to 1.0,
    "requires_verification": True | False
}
```

## Evaluation Pipeline (Planned)

1. **Pre-filter**: Remove obviously irrelevant updates
2. **Classify**: Determine update type (capability/constraint/pricing)
3. **Score**: Assign importance score based on criteria
4. **Verify**: Flag updates requiring experimental validation
5. **Prioritize**: Rank for weekly report inclusion

## Current Status

🚧 **Not yet implemented** - Placeholder directory for future development

## Next Steps

1. Define evaluation rubric and scoring system
2. Implement keyword/pattern-based classifiers
3. Add ML-based classification (if needed)
4. Create confidence scoring logic
5. Build verification requirement detector

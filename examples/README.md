# Kura Dataset Examples

This directory contains comprehensive examples of running Kura on large-scale conversation datasets to discover patterns, topics, and insights at scale.

## Available Examples

### 🌍 [WildChat Analysis](./wildchat/) 
**Real User Conversations at Scale**

Analyze **50,000 authentic user conversations** from the WildChat dataset (529k total) to understand:

- **What users actually want** from AI assistants
- **Popular topics and trends** in real-world AI usage
- **Language diversity** and global conversation patterns  
- **Authentic interaction styles** and user behavior

**Key Insights from 5k Analysis:**
- 200 distinct topic clusters discovered
- Top themes: cryptocurrency, programming, creative writing, professional development
- Multi-language support (English, Chinese, Korean, etc.)
- Processing rate: 12+ conversations/second

[**→ Run WildChat Analysis**](./wildchat/README.md)

---

### 🎯 [LMSYS Analysis](./lmsys/)
**Model Evaluation and Human Preferences**

Analyze **evaluation conversations and human judgments** from LMSYS datasets to understand:

- **How AI models are evaluated** by researchers and users
- **Human preference patterns** in model comparison  
- **Evaluation task types** and assessment criteria
- **Model performance insights** across different capabilities

**Focus Areas:**
- MT-Bench human evaluations
- Chatbot Arena comparison data
- Structured evaluation scenarios
- Quality assessment patterns

[**→ Run LMSYS Analysis**](./lmsys/README.md)

## Key Differences

| Aspect | WildChat | LMSYS |
|--------|----------|--------|
| **Data Type** | Real user conversations | Structured evaluations |
| **Scale** | 529k+ conversations | ~3k focused evaluations |
| **Purpose** | Understanding usage patterns | Understanding model capabilities |
| **Insights** | What people actually want | How models are assessed |
| **Language** | Multi-language, authentic | Primarily English, structured |
| **Clusters** | 200+ diverse topics | 50-100 evaluation tasks |

## Getting Started

### Quick Start
```bash
# Install Kura
uv pip install -e ".[dev]"

# Run WildChat analysis (real user conversations)
python examples/wildchat/run.py

# Run LMSYS analysis (model evaluation)  
python examples/lmsys/run.py
```

### Expected Performance

**WildChat (50k conversations):**
- Processing time: ~20-25 minutes
- Clusters found: ~1,500 topics
- Insights: Real-world usage patterns

**LMSYS (3k evaluations):**
- Processing time: ~10-15 minutes  
- Clusters found: ~200 evaluation tasks
- Insights: Model assessment patterns

## Research Applications

### Understanding AI Usage
- **Product Development**: What features do users actually need?
- **Content Strategy**: What topics are most popular?
- **User Research**: How do people naturally interact with AI?
- **Trend Analysis**: What are emerging use cases?

### Model Evaluation
- **Benchmark Design**: What evaluation tasks matter most?
- **Quality Assessment**: What drives human preferences?
- **Model Selection**: Which models excel at which tasks?
- **Bias Detection**: Are evaluations fair and comprehensive?

## Comparative Analysis

Run both analyses to compare **real usage vs. evaluation patterns**:

```python
# Load results from both analyses
wildchat_results = load_analysis_results("wildchat_results/")
lmsys_results = load_analysis_results("lmsys_results/")

# Compare cluster themes
usage_themes = extract_themes(wildchat_results)
eval_themes = extract_themes(lmsys_results)

# Identify gaps between usage and evaluation
gaps = find_evaluation_gaps(usage_themes, eval_themes)
```

### Example Insights:

**Usage vs Evaluation Gaps:**
- Users frequently ask about crypto → Few crypto evaluation tasks
- Creative writing is popular → Limited creativity benchmarks  
- Technical debugging common → Evaluation focuses on correctness over helpfulness

## Configuration Options

Both examples support extensive customization:

### Data Filtering
```python
# Filter by language
conversations = filter_by_language(conversations, ["English", "Chinese"])

# Filter by toxicity
conversations = filter_toxic_content(conversations, exclude_toxic=True)

# Filter by model type  
conversations = filter_by_model(conversations, ["gpt-4", "claude"])
```

### Clustering Parameters
```python
clustering_method = MiniBatchKmeansClusteringMethod(
    clusters_per_group=50,    # Larger = fewer, broader clusters
    batch_size=1000,         # Processing efficiency
    max_iter=200,            # Convergence iterations
)
```

### Scale Options
```python
# For development/testing
num_conversations = 1000

# For research analysis  
num_conversations = 10000

# For production insights
num_conversations = 50000
```

## Results Format

Both analyses generate comprehensive results:

```
results/
├── analysis_summary.json       # High-level statistics  
├── cluster_details.json        # Detailed cluster information
├── summaries.jsonl            # Individual conversation summaries
├── clusters.jsonl             # Raw cluster data
└── visualization_data.json    # Data for plotting and analysis
```

## Next Steps

1. **Start with WildChat** to understand real user behavior
2. **Follow with LMSYS** to understand evaluation patterns
3. **Compare results** to identify research opportunities
4. **Scale up** to full datasets for production insights
5. **Customize analysis** for your specific research questions

---

**Ready to discover conversation patterns at massive scale?** Choose your analysis and start uncovering insights from real-world AI interactions!
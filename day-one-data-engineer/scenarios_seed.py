"""
Seed data for Day One: Data Engineer scenarios.
Run this script to populate the scenarios and skills tables.
"""

import json
import lakebase


# Scenario S1: "The Monday Morning Red Dashboard" (incident_debugging)
S1_DEFINITION = {
    "start_node": "node_1",
    "nodes": {
        "node_1": {
            "type": "decision",
            "narrative": """
**Monday, 8:05 AM**

You arrive to find Slack has four unread messages. The nightly ingestion from 3 of 12 source systems failed. Your team lead posted 10 minutes ago:

> "Status on the ingestion failures? Client's weekly report goes out at noon."

You don't know the details yet. The dashboard is red.

**What's your first move?**
            """,
            "options": [
                "read_logs",
                "rerun_pipeline",
                "reply_slack",
                "check_report_partial"
            ],
            "option_labels": {
                "read_logs": "Dive into the error logs immediately",
                "rerun_pipeline": "Rerun the failed pipelines and see what happens",
                "reply_slack": "Acknowledge in Slack with an ETA, then investigate",
                "check_report_partial": "Check if the report can go out with 9/12 sources"
            },
            "rubric": {
                "options": {
                    "read_logs": 0.7,
                    "rerun_pipeline": 0.3,
                    "reply_slack": 0.9,
                    "check_report_partial": 0.6
                }
            },
            "feedback": {
                "read_logs": "Reasonable, but your team lead is waiting. A quick acknowledgment buys you time and keeps everyone calm.",
                "rerun_pipeline": "⚠️ Rerunning blind is a classic trap. You might waste an hour hitting the same error. Check the logs first.",
                "reply_slack": "✅ Smart. You're managing expectations while giving yourself space to investigate properly.",
                "check_report_partial": "Good instinct to think about workarounds, but tell your lead what you're doing first."
            },
            "next": {
                "read_logs": "node_2",
                "rerun_pipeline": "node_2",
                "reply_slack": "node_2",
                "check_report_partial": "node_2"
            },
            "search_evidence": True,
            "evidence_query": "debugging production pipeline failures"
        },
        "node_2": {
            "type": "decision",
            "narrative": """
You pull up the logs. Three sources failed:

1. **Source A (authentication error)**: "Invalid credentials for API endpoint"
2. **Source B (schema mismatch)**: "Unexpected column 'compliance_flag' in table customers"
3. **Source C (timeout)**: "Connection timeout after 30s"

**Which do you triage first and why?**
            """,
            "options": [
                "auth_first",
                "schema_first",
                "timeout_first",
                "check_impact"
            ],
            "option_labels": {
                "auth_first": "Authentication - likely a quick fix (token refresh)",
                "schema_first": "Schema mismatch - might break downstream joins",
                "timeout_first": "Timeout - could be infrastructure, affects reliability",
                "check_impact": "Check which failure blocks the report most"
            },
            "rubric": {
                "options": {
                    "auth_first": 0.8,
                    "schema_first": 0.6,
                    "timeout_first": 0.5,
                    "check_impact": 1.0
                }
            },
            "feedback": {
                "auth_first": "✅ Good instinct. Auth errors are usually quick wins - expired token, changed password. Fix this first.",
                "schema_first": "Schema changes need human coordination upstream. This might take hours. Not your first target under time pressure.",
                "timeout_first": "Timeouts can be tricky - network issues, source system slowness. Not the fastest win.",
                "check_impact": "🎯 Perfect. You're prioritizing by business impact, not just technical ease. This is senior-level thinking."
            },
            "next": {
                "auth_first": "node_3",
                "schema_first": "node_3",
                "timeout_first": "node_3",
                "check_impact": "node_3"
            },
            "search_evidence": True,
            "evidence_query": "handling schema drift in data pipelines"
        },
        "node_3": {
            "type": "decision",
            "narrative": """
You've fixed the auth error (token refresh). The schema mismatch remains:

Source B added a column `compliance_flag` mid-week without telling anyone. Your pipeline expects a fixed schema.

**How do you handle this?**
            """,
            "options": [
                "drop_column",
                "schema_tolerant",
                "email_wait"
            ],
            "option_labels": {
                "drop_column": "Hardcode-drop the new column and ingest the rest",
                "schema_tolerant": "Make ingestion schema-tolerant, notify the owner",
                "email_wait": "Email the source owner and wait for guidance"
            },
            "rubric": {
                "options": {
                    "drop_column": 0.4,
                    "schema_tolerant": 1.0,
                    "email_wait": 0.3
                }
            },
            "feedback": {
                "drop_column": "⚠️ This fixes it now but silently drops data. What if that column is important? You won't know until someone asks for it.",
                "schema_tolerant": "✅ Perfect. You're building resilience AND communicating. This is the right balance of urgency and quality.",
                "email_wait": "You don't have time to wait. The report is due at noon. Act now, coordinate later."
            },
            "next": {
                "drop_column": "node_4",
                "schema_tolerant": "node_4",
                "email_wait": "node_4"
            },
            "search_evidence": True,
            "evidence_query": "spark schema evolution mergeSchema option"
        },
        "node_4": {
            "type": "free_text",
            "narrative": """
It's 11:30 AM. You've fixed Sources A and B. Source C (timeout) is still down - it's a vendor API having issues.

Your team lead asks:

> "Status update? Can we ship the report?"

**What do you tell the stakeholder?**
            """,
            "rubric": {
                "criteria": [
                    "Honest about what's fixed and what's not",
                    "Offers options (partial report, delay, workaround)",
                    "Doesn't over-promise or make heroic claims"
                ]
            },
            "next": None,
            "search_evidence": False
        }
    }
}

# Scenario S2: "The Number Is 40x Too Big" (data_quality)
S2_DEFINITION = {
    "start_node": "node_1",
    "nodes": {
        "node_1": {
            "type": "decision",
            "narrative": """
**Monday, 9:15 AM**

You arrive to find a Slack DM from your team lead:

> "Client noticed their revenue reconciliation report shows Entity X at $42M when they expected ~$1M. They're freaking out. Can you take a look?"

You inherited this pipeline from a colleague who left last month. Documentation is thin. The report pulls from a table you built last week, and everything looked fine in your spot checks.

**What's your first move?**
            """,
            "options": [
                "check_report_sql",
                "check_source_data",
                "check_transform_layer",
                "ask_client_expected"
            ],
            "option_labels": {
                "check_report_sql": "Check the report SQL - maybe a join is wrong",
                "check_source_data": "Check the source data - is it already inflated?",
                "check_transform_layer": "Check the transformation layer in the middle",
                "ask_client_expected": "Ask the client what number they expected"
            },
            "rubric": {
                "options": {
                    "check_report_sql": 0.5,
                    "check_source_data": 0.9,
                    "check_transform_layer": 0.7,
                    "ask_client_expected": 0.6
                }
            },
            "feedback": {
                "check_report_sql": "Reasonable instinct, but you're starting at the end. If the source is already wrong, you'll waste time debugging a correct query.",
                "check_source_data": "✅ Smart. You're bracketing the problem: is the source right and transform wrong, or is the source already inflated? This saves time.",
                "check_transform_layer": "Not bad - but checking the source first would tell you whether the bug is upstream or downstream. You might be debugging correct code.",
                "ask_client_expected": "Good to understand expectations, but you need data first. Their 'expected' number might also be wrong."
            },
            "next": {
                "check_report_sql": "node_2",
                "check_source_data": "node_2",
                "check_transform_layer": "node_2",
                "ask_client_expected": "node_2"
            },
            "search_evidence": True,
            "evidence_query": "debugging incorrect aggregate values sql"
        },
        "node_2": {
            "type": "decision",
            "narrative": """
You pull up the pipeline. The source data looks plausible - sample rows show reasonable revenue figures. The transform layer includes a currency conversion step that joins to a rates table.

You sample 10 rows from the rates table:

```
currency | rate_date   | rate
-------- | ----------- | ------
USD      | 2024-01-15  | 1.0000
EUR      | 2024-01-15  | 0.9200
JPY      | 2024-01-15  | 0.0091  <-- This looks suspicious
GBP      | 2024-01-15  | 1.2700
```

The JPY rate is 0.0091 instead of ~110 (the inverse). Entity X has transactions in JPY.

**What's your hypothesis?**
            """,
            "options": [
                "bad_rates_source",
                "scaling_factor_ignored",
                "duplicate_joins"
            ],
            "option_labels": {
                "bad_rates_source": "The rates source is feeding us bad data",
                "scaling_factor_ignored": "Some currencies use scaling factors we're ignoring",
                "duplicate_joins": "Maybe the join is duplicating rows"
            },
            "rubric": {
                "options": {
                    "bad_rates_source": 0.4,
                    "scaling_factor_ignored": 1.0,
                    "duplicate_joins": 0.3
                }
            },
            "feedback": {
                "bad_rates_source": "Possible, but that rate IS technically correct - it's just the minor unit representation. JPY rates are stored as 1/100th scale in many systems.",
                "scaling_factor_ignored": "✅ Exactly right. Currencies like JPY are stored in minor units in some systems. The rate 0.0091 needs a factor of 100 multiplied back in.",
                "duplicate_joins": "Duplicate joins would multiply the rows, not divide by 100. Check the row counts - they match."
            },
            "next": {
                "bad_rates_source": "node_3",
                "scaling_factor_ignored": "node_3",
                "duplicate_joins": "node_3"
            },
            "search_evidence": True,
            "evidence_query": "currency conversion rate scaling factor"
        },
        "node_3": {
            "type": "decision",
            "narrative": """
You've identified the root cause: the rates table is missing a `scale_factor` column that some currencies need (JPY factor = 100, most others = 1).

**How do you fix it?**
            """,
            "options": [
                "patch_jpy_only",
                "handle_factors_generically",
                "add_validation_check"
            ],
            "option_labels": {
                "patch_jpy_only": "Patch JPY specifically in the query",
                "handle_factors_generically": "Add a scale_factor column to the rates table",
                "add_validation_check": "Add validation checks for implausible rates"
            },
            "rubric": {
                "options": {
                    "patch_jpy_only": 0.5,
                    "handle_factors_generically": 0.9,
                    "add_validation_check": 1.0
                }
            },
            "feedback": {
                "patch_jpy_only": "This fixes Entity X, but you'll hit this again with other currencies. Better to handle it generically.",
                "handle_factors_generically": "✅ Good. This prevents the same bug for other currencies.",
                "add_validation_check": "🎯 Perfect. Both fix AND prevention. Catches similar issues early."
            },
            "next": {
                "patch_jpy_only": "node_4",
                "handle_factors_generically": "node_4",
                "add_validation_check": "node_4"
            },
            "search_evidence": True,
            "evidence_query": "data quality validation checks sql"
        },
        "node_4": {
            "type": "free_text",
            "narrative": """
You've implemented the fix and rerun the report. Entity X now shows $1.05M - much closer to expected.

The client replies:

> "Thank you! But how do we know this won't happen again? What if other currencies have this problem?"

**What do you tell them?**
            """,
            "rubric": {
                "criteria": [
                    "Explains the root cause (currency scaling factors)",
                    "Describes the prevention (generic scale_factor handling)",
                    "Mentions detection (validation checks or testing strategy)"
                ]
            },
            "next": None,
            "search_evidence": False
        }
    }
}

# Scenario S3: "The Metric That Doesn't Exist" (stakeholder_communication)
S3_DEFINITION = {
    "start_node": "node_1",
    "nodes": {
        "node_1": {
            "type": "decision",
            "narrative": """
**Tuesday, 2 PM - Slack DM from Business Stakeholder**

> "Hey! Can you add 'supplier reliability score by month' to the dashboard by Friday? Should be straightforward - just need the numbers. Thanks!"

You've never heard of this metric. You check the data model - no such field exists anywhere.

**What's your first response?**
            """,
            "options": [
                "say_yes",
                "say_no_exist",
                "ask_decision"
            ],
            "option_labels": {
                "say_yes": "'Sure, I'll figure it out!' (say yes, sort it out later)",
                "say_no_exist": "'That field doesn't exist in our data'",
                "ask_decision": "'What decision are you trying to make with this metric?'"
            },
            "rubric": {
                "options": {
                    "say_yes": 0.3,
                    "say_no_exist": 0.5,
                    "say_no_exist": 1.0
                }
            },
            "feedback": {
                "say_yes": "⚠️ You just committed to building something you don't understand. This is how bad metrics get deployed.",
                "say_no_exist": "Technically true, but not helpful. They don't care that it doesn't exist - they care about the decision they're trying to make.",
                "ask_decision": "🎯 Perfect. You're uncovering the *actual* requirement before building anything. This is the whole game."
            },
            "next": {
                "say_yes": "node_2",
                "say_no_exist": "node_2",
                "ask_decision": "node_2"
            },
            "search_evidence": True,
            "evidence_query": "defining business metrics requirements"
        },
        "node_2": {
            "type": "free_text",
            "narrative": """
They reply:

> "We want to know which suppliers keep missing delivery dates. We need to hold them accountable."

You have `order_date` and `delivery_date` in your orders table.

**Propose a definition for 'supplier reliability score'.**

(Make your assumptions explicit: late threshold, minimum order count, time window, etc.)
            """,
            "rubric": {
                "criteria": [
                    "Defines what 'late' means (e.g., delivery_date > order_date + X days)",
                    "Considers minimum order count to avoid small-sample bias",
                    "Specifies time window (last 30/90/365 days)",
                    "States the metric clearly (e.g., % on-time deliveries)"
                ]
            },
            "next": "node_3",
            "search_evidence": True,
            "evidence_query": "calculating delivery performance metrics sql"
        },
        "node_3": {
            "type": "decision",
            "narrative": """
You propose:

> "Reliability Score = (on-time deliveries / total deliveries) over the last 90 days, minimum 10 orders to qualify."

They love it. But as you start building, you realize:
- **Full implementation** (handling edge cases, nulls, time zones, partial deliveries) = 3 days
- **Simple proxy** (just count late vs on-time, ignore edge cases) = half a day

**What do you offer?**
            """,
            "options": [
                "full_only",
                "simple_only",
                "proxy_plus_roadmap"
            ],
            "option_labels": {
                "full_only": "The full solution - we'll ship Friday next week",
                "simple_only": "The simple proxy - it's ready tomorrow",
                "proxy_plus_roadmap": "Proxy now, full solution on the roadmap with stated tradeoffs"
            },
            "rubric": {
                "options": {
                    "full_only": 0.5,
                    "simple_only": 0.6,
                    "proxy_plus_roadmap": 1.0
                }
            },
            "feedback": {
                "full_only": "They wanted it by Friday. You just delayed their decision by a week. Was the perfect the enemy of the good here?",
                "simple_only": "Gets them something fast, but what if the edge cases matter? You didn't tell them what they're NOT getting.",
                "proxy_plus_roadmap": "✅ Perfect. You're delivering fast AND being honest about limitations. This is how you build trust."
            },
            "next": {
                "full_only": "node_4",
                "simple_only": "node_4",
                "proxy_plus_roadmap": "node_4"
            },
            "search_evidence": False
        },
        "node_4": {
            "type": "decision",
            "narrative": """
A week later, the stakeholder messages you:

> "Why does Supplier X score so badly? Everyone knows they're great. Something must be wrong with your data."

**What do you do?**
            """,
            "options": [
                "defend_data",
                "investigate_first"
            ],
            "option_labels": {
                "defend_data": "Defend the data - 'The numbers are what they are'",
                "investigate_first": "Investigate before responding - check Supplier X's orders"
            },
            "rubric": {
                "options": {
                    "defend_data": 0.3,
                    "investigate_first": 1.0
                }
            },
            "feedback": {
                "defend_data": "⚠️ Defensive posture. What if they're right? Metrics CAN be misleading. Always investigate anomalies.",
                "investigate_first": "✅ Perfect. You find Supplier X had one massive order that was late, skewing the rate. This is analytical humility."
            },
            "next": {
                "defend_data": None,
                "investigate_first": None
            },
            "search_evidence": True,
            "evidence_query": "weighted vs unweighted metrics small sample bias"
        }
    }
}

# Scenario S4: "Twelve Sources, One Table" (pipeline_design)
S4_DEFINITION = {
    "start_node": "node_1",
    "nodes": {
        "node_1": {
            "type": "decision",
            "narrative": """
**Project Kickoff: Consolidate Journal Data**

You must consolidate journal entry data from 12 different ERP systems into one table. Each system has:
- Different key formats (some numeric IDs, some alphanumeric)
- Different column names for the same concepts
- Different granularity (some daily, some transaction-level)

Greenfield design - no legacy to maintain.

**How do you handle primary keys across systems?**
            """,
            "options": [
                "global_id",
                "composite_keys",
                "hash_everything"
            ],
            "option_labels": {
                "global_id": "Force a global ID - make all systems use the same format",
                "composite_keys": "Composite keys: (source_system, source_id)",
                "hash_everything": "Hash all natural keys into UUIDs"
            },
            "rubric": {
                "options": {
                    "global_id": 0.4,
                    "composite_keys": 0.9,
                    "hash_everything": 0.7
                }
            },
            "feedback": {
                "global_id": "Forcing 12 systems to adopt a new ID scheme? That's months of coordination and high collision risk.",
                "composite_keys": "✅ Smart. You're preserving source identity and avoiding the 'vendor IDs are globally unique' trap (they're not).",
                "hash_everything": "Works, but you lose the ability to trace back to the source system easily. Debugging gets harder."
            },
            "next": {
                "global_id": "node_2",
                "composite_keys": "node_2",
                "hash_everything": "node_2"
            },
            "search_evidence": True,
            "evidence_query": "composite keys data warehousing multiple sources"
        },
        "node_2": {
            "type": "decision",
            "narrative": """
**Ingestion Strategy Challenge**

You learn:
- Source A sends **full snapshots** every night
- Source B sends **deltas only** (changes since last run)
- Source C **can't tell you** which records changed

**How do you design the ingestion contract?**
            """,
            "options": [
                "force_one_pattern",
                "adapt_per_source",
                "convert_all_delta"
            ],
            "option_labels": {
                "force_one_pattern": "Force all 12 sources to use the same pattern (snapshots)",
                "adapt_per_source": "Handle each source differently based on what they can provide",
                "convert_all_delta": "Convert snapshots to deltas on your side"
            },
            "rubric": {
                "options": {
                    "force_one_pattern": 0.3,
                    "adapt_per_source": 1.0,
                    "convert_all_delta": 0.7
                }
            },
            "feedback": {
                "force_one_pattern": "Source systems won't change for you. You need to meet them where they are.",
                "adapt_per_source": "🎯 Perfect. You're building a flexible ingestion layer that handles heterogeneity. This is real-world data engineering.",
                "convert_all_delta": "Smart for processing efficiency, but you need the snapshot→delta logic to be solid. Adds complexity."
            },
            "next": {
                "force_one_pattern": "node_3",
                "adapt_per_source": "node_3",
                "convert_all_delta": "node_3"
            },
            "search_evidence": True,
            "evidence_query": "incremental vs full load data ingestion patterns"
        },
        "node_3": {
            "type": "decision",
            "narrative": """
**Architecture Decision: Transform on Ingest?**

A teammate suggests:

> "Let's transform everything to the target schema during ingestion. Makes downstream queries simpler."

You've read about medallion architecture (bronze → silver → gold).

**What do you argue for?**
            """,
            "options": [
                "transform_on_ingest",
                "keep_bronze_raw"
            ],
            "option_labels": {
                "transform_on_ingest": "Transform on ingest - simpler for consumers",
                "keep_bronze_raw": "Keep bronze raw, conform in silver layer"
            },
            "rubric": {
                "options": {
                    "transform_on_ingest": 0.5,
                    "keep_bronze_raw": 1.0
                }
            },
            "feedback": {
                "transform_on_ingest": "Convenient now, but what if your transform logic was wrong? You've lost the raw data. Replayability matters.",
                "keep_bronze_raw": "✅ Perfect. You're preserving the source of truth. If your transforms have bugs, you can replay from bronze without re-ingesting."
            },
            "next": {
                "transform_on_ingest": "node_4",
                "keep_bronze_raw": "node_4"
            },
            "search_evidence": True,
            "evidence_query": "medallion architecture bronze silver gold"
        },
        "node_4": {
            "type": "free_text",
            "narrative": """
**Validation Strategy**

The client asks:

> "How do we know the consolidation is correct? How do we trust this combined table?"

**What's your validation strategy?**
            """,
            "rubric": {
                "criteria": [
                    "Reconciliation totals per source (row counts, sum of amounts)",
                    "Sample-based spot checks against source systems",
                    "A validation deliverable or report (not just 'trust me')",
                    "Ongoing monitoring or data quality checks"
                ]
            },
            "next": None,
            "search_evidence": True,
            "evidence_query": "data validation reconciliation checks"
        }
    }
}

# Scenario S5: "The Job That Eats All the Memory" (performance_optimization)
S5_DEFINITION = {
    "start_node": "node_1",
    "nodes": {
        "node_1": {
            "type": "decision",
            "narrative": """
**Production Issue: OOM Errors**

An extraction job pulls a large table via an external API. It worked fine when the table had 10M rows. Now at 40M rows, it dies with:

```
java.lang.OutOfMemoryError: Java heap space
```

The job reruns from zero every time it fails.

**What's your first instinct?**
            """,
            "options": [
                "more_memory",
                "reduce_memory_usage",
                "understand_extraction"
            ],
            "option_labels": {
                "more_memory": "Give the cluster more memory",
                "reduce_memory_usage": "Reduce what's held in memory",
                "understand_extraction": "Read how the extraction code actually works"
            },
            "rubric": {
                "options": {
                    "more_memory": 0.3,
                    "reduce_memory_usage": 0.7,
                    "understand_extraction": 1.0
                }
            },
            "feedback": {
                "more_memory": "⚠️ Classic junior trap. This works until 60M rows, then 80M. You're delaying the problem, not solving it.",
                "reduce_memory_usage": "Good direction, but *what* should you reduce? You need to understand the code first.",
                "understand_extraction": "✅ Perfect. You're diagnosing before prescribing. Most OOM issues are algorithmic, not resource problems."
            },
            "next": {
                "more_memory": "node_2",
                "reduce_memory_usage": "node_2",
                "understand_extraction": "node_2"
            },
            "search_evidence": True,
            "evidence_query": "java out of memory spark large dataset"
        },
        "node_2": {
            "type": "decision",
            "narrative": """
You find the code:

```python
result = api_client.fetch_all(table_name)  # Returns full result set
df = spark.createDataFrame(result)
df.write.parquet(output_path)
```

It's loading the **entire** result set into memory before writing.

**How do you fix this?**
            """,
            "options": [
                "chunk_by_range",
                "stream_to_disk",
                "paginate_api"
            ],
            "option_labels": {
                "chunk_by_range": "Chunk by primary key ranges (e.g., ID 1-100k, 100k-200k...)",
                "stream_to_disk": "Stream to disk incrementally instead of holding in memory",
                "paginate_api": "Use the API's pagination to fetch in batches"
            },
            "rubric": {
                "options": {
                    "chunk_by_range": 0.8,
                    "stream_to_disk": 0.9,
                    "paginate_api": 1.0
                }
            },
            "feedback": {
                "chunk_by_range": "✅ Good. You're breaking the problem into manageable pieces. Works if IDs are sequential.",
                "stream_to_disk": "✅ Good. You're avoiding the memory accumulation. Pairs well with pagination.",
                "paginate_api": "🎯 Perfect. This is the API's designed usage pattern. Most have page_size and offset parameters."
            },
            "next": {
                "chunk_by_range": "node_3",
                "stream_to_disk": "node_3",
                "paginate_api": "node_3"
            },
            "search_evidence": True,
            "evidence_query": "spark paginated api extraction pattern"
        },
        "node_3": {
            "type": "decision",
            "narrative": """
**Resilience Problem**

You implement chunking. It works! But a failure at chunk 61 of 80 restarts everything.

**What do you add?**
            """,
            "options": [
                "checkpointing",
                "ignore_resume"
            ],
            "option_labels": {
                "checkpointing": "Checkpointing - track which chunks succeeded, resume from failure",
                "ignore_resume": "Just let it re-run; it's fast enough now"
            },
            "rubric": {
                "options": {
                    "checkpointing": 1.0,
                    "ignore_resume": 0.5
                }
            },
            "feedback": {
                "checkpointing": "✅ Perfect. This is the OOM-to-checkpointing learning arc. You're building idempotent, resumable jobs.",
                "ignore_resume": "Works until it doesn't. What if chunk 79 keeps failing? You waste hours re-processing 78 successful chunks."
            },
            "next": {
                "checkpointing": "node_4",
                "ignore_resume": "node_4"
            },
            "search_evidence": True,
            "evidence_query": "checkpointing idempotent data pipeline jobs"
        },
        "node_4": {
            "type": "decision",
            "narrative": """
**Tradeoff Question**

Your fix works reliably. But it makes the job 20% slower overall (more API calls, coordination overhead).

Your lead asks:

> "Is that acceptable?"

**What do you say?**
            """,
            "options": [
                "reliability_over_speed",
                "try_optimize_both"
            ],
            "option_labels": {
                "reliability_over_speed": "Yes - reliability > raw speed for nightly batch",
                "try_optimize_both": "Let me try to optimize both speed and reliability"
            },
            "rubric": {
                "options": {
                    "reliability_over_speed": 1.0,
                    "try_optimize_both": 0.7
                }
            },
            "feedback": {
                "reliability_over_speed": "✅ Perfect. You're stating the actual requirement ('done by 6am') instead of chasing 'as fast as possible.'",
                "try_optimize_both": "Not wrong, but over-engineering risk. If it's done by 6am, that's success. Don't gold-plate."
            },
            "next": {
                "reliability_over_speed": None,
                "try_optimize_both": None
            },
            "search_evidence": False
        }
    }
}


def seed_scenarios():
    """Seed the scenarios table."""
    scenarios = [
        {
            "scenario_id": "monday_morning_red_dashboard",
            "title": "The Monday Morning Red Dashboard",
            "category": "incident_debugging",
            "difficulty": 3,
            "est_minutes": 12,
            "definition": S1_DEFINITION,
        },
        {
            "scenario_id": "number_40x_too_big",
            "title": "The Number Is 40x Too Big",
            "category": "data_quality",
            "difficulty": 3,
            "est_minutes": 15,
            "definition": S2_DEFINITION,
        },
        {
            "scenario_id": "metric_doesnt_exist",
            "title": "The Metric That Doesn't Exist",
            "category": "stakeholder_communication",
            "difficulty": 4,
            "est_minutes": 18,
            "definition": S3_DEFINITION,
        },
        {
            "scenario_id": "twelve_sources_one_table",
            "title": "Twelve Sources, One Table",
            "category": "pipeline_design",
            "difficulty": 4,
            "est_minutes": 20,
            "definition": S4_DEFINITION,
        },
        {
            "scenario_id": "job_eats_memory",
            "title": "The Job That Eats All the Memory",
            "category": "performance_optimization",
            "difficulty": 4,
            "est_minutes": 16,
            "definition": S5_DEFINITION,
        },
    ]
    
    for scenario in scenarios:
        rows = lakebase.run_query(
            "SELECT scenario_id FROM scenarios WHERE title = %s",
            (scenario["title"],)
        )
        
        if rows:
            print(f"✓ Scenario '{scenario['title']}' already exists")
            continue
        
        definition_json = json.dumps(scenario["definition"])
        lakebase.run_write(
            """
            INSERT INTO scenarios (scenario_id, title, category, difficulty, est_minutes, definition)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (scenario["scenario_id"], scenario["title"], scenario["category"], scenario["difficulty"], 
             scenario["est_minutes"], definition_json)
        )
        print(f"✅ Seeded: {scenario['title']}")


def seed_skills():
    """Seed the skills table."""
    skills = [
        ("triage", "incident_debugging", "Prioritizing issues under pressure"),
        ("systematic_debugging", "data_quality", "Methodical root cause analysis"),
        ("schema_evolution", "incident_debugging", "Handling upstream schema changes"),
        ("requirements_elicitation", "stakeholder_communication", "Extracting clear requirements"),
        ("data_modeling", "pipeline_design", "Designing normalized schemas"),
        ("defensive_design", "pipeline_design", "Building fault-tolerant pipelines"),
        ("performance_tuning", "performance_optimization", "Optimizing resource usage"),
        ("communication", "stakeholder_communication", "Clear technical communication"),
    ]
    
    for name, category, description in skills:
        rows = lakebase.run_query(
            "SELECT skill_id FROM skills WHERE name = %s",
            (name,)
        )
        if rows:
            continue
        
        lakebase.run_write(
            "INSERT INTO skills (name, category, description) VALUES (%s, %s, %s)",
            (name, category, description)
        )
    
    print(f"✅ Seeded {len(skills)} skills")


if __name__ == "__main__":
    print("\n🌱 Seeding Day One: Data Engineer database...")
    print("=" * 60)
    seed_scenarios()
    seed_skills()
    print("=" * 60)
    print("✅ Database seeded successfully!\n")

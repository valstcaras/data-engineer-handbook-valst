"""
Seed data for Day One: Data Engineer scenarios.
Run this script to populate the scenarios and skills tables.
"""

import json
import sys
sys.path.append('/Workspace/Users/valeria.s.caras@gmail.com/data-engineer-handbook-valst/day-one-data-engineer')

import lakebase


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


def seed_scenarios():
    """Seed the scenarios table."""
    scenarios = [
        {
            "title": "The Number Is 40x Too Big",
            "category": "data_quality",
            "difficulty": 3,
            "est_minutes": 15,
            "definition": S2_DEFINITION,
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
            INSERT INTO scenarios (title, category, difficulty, est_minutes, definition)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (scenario["title"], scenario["category"], scenario["difficulty"], 
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

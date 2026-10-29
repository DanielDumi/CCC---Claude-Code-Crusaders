# backend/tools/

The tools the investigation agent may ask for, and a fake server that answers them from synthetic data.

## `catalog.py`

A static catalogue, registered by an administrator (`CATALOG`). Each `ToolSpec` has an id, a description, argument names, a data category, a source reference, `read_only=True`, and `key_args` (which arguments form the lookup key).

| Tool | Data category | Used for |
|---|---|---|
| `company_registry_lookup` | `CORPORATE_PUBLIC` | Confirm the legal entity (identity) |
| `legal_case_status_lookup` | `CORPORATE_LEGAL` | Current status of a court case |
| `document_metadata_lookup` | `DOCUMENT_METADATA` | Which document version is approved |
| `document_signature_check` | `DOCUMENT_METADATA` | Authenticity of a record (simulated) |
| `financial_report_lookup` | `CORPORATE_FINANCIAL` | Filed figures per year |
| `tax_status_lookup` | `CORPORATE_TAX` | Tax obligations |
| `doc_read` | `PERSONAL_DOCUMENT_FIELDS` | Read a document as typed fields (payslip, bank statement) |
| `consent_lookup` | `CONSENT_RECORD` | Client consent records |
| `application_status_lookup` | `APPLICATION_STATUS` | Status of the application |
| `anaf_income_query` | `PERSONAL_INCOME` | ANAF income data; needs a valid consent |
| `unrestricted_web_search` | `PERSONAL_DATA` | **Exists only so the deny path can be shown.** Disabled in the catalogue and hard-denied by policy |

`catalog_for_model()` is what the planner's model sees: ids, descriptions, argument names, categories. No endpoints, no credentials.

Which tools are allowed, for which source and category, with which conditions, is decided by `allowed_tools` / `deny_tools` in `fixtures/policies/demo-policy.yaml`, not here.

## `mcp_fixture_server.py`

`FakeMCPServer` stands in for the bank's read-only MCP servers. `call(scenario_id, tool_id, arguments)` looks up the record for the key arguments in the scenario's `tool_data` (or a `*` default) and returns it with the tool's source and category.

- `invocations` counts calls per tool. Tests use it to prove that a denied request **never reached** the server (`total_invocations == 0`).
- `fail_modes` makes a tool time out on demand (the "Make the court registry time out" button), to show that a failed source gives `INSUFFICIENT_EVIDENCE`, never `SUPPORTED`.
- An unknown key raises `ToolUnavailable`: the tool knows only what the fixture contains.

Only `ToolProxy` may call `call()`. In production this module would be replaced by connections to the bank's approved MCP servers; the catalogue, the policy and the gate stay the same.

## Adding a tool

1. Add a `ToolSpec` to `CATALOG` (read-only, data category, source ref, key args).
2. Add it to `allowed_tools` in the policy YAML with its source and categories.
3. Add records to the scenario's `tool_data`.
4. Add a test for the allowed path and the denied path (zero invocations).

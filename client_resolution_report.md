# AxionX Client Resolution Diagnostic Report

## 1. CSV Column Names Used for Client Resolution

| Column | Staging Field | Used For |
|--------|--------------|----------|
| `Description` | `parsed_client_name` (regex-extracted) | Primary client name source — 15+ regex patterns extract lender name |
| `Company` | `company` | Fallback — the borrower's company, NOT the lender; only tried when parser returns empty |
| `Account ID` | `geoop_account_id` | Always `17071` (GeoOp tenant ID) — never used for client matching |

## 2. Client Resolution Precedence Order

```
import_staged_jobs() → for each job:
  1. parsed_client_name (from parse_description(Description))
     → _match_client(conn, parsed_client_name)
  2. IF step 1 returned None AND Company is non-empty:
     → _match_client(conn, Company)
  3. IF both return None → client_id = NULL
```
**No client auto-creation.** `_match_client()` is match-only — it never creates stub clients.

## 3. Normalisation Applied in _match_client()

### Tier 1: Exact case-insensitive
- Input is trimmed and lowercased
- Compared against `LOWER(clients.name)` for each Axion client

### Tier 2: Normalised comparison
- Lowercase + strip whitespace
- Suffix removal: `Pty Ltd`, `Pty. Ltd.`, `Limited`, `Ltd`, `Inc`, `Finance`, `Leasing`
- Remove all non-alphanumeric except spaces
- Collapse multiple spaces to single space
- Example: `Macquarie Leasing Pty Ltd` → `macquarie`

### Tier 3: Multi-word overlap
- Requires ≥2 shared words between input and candidate
- First word of input must appear in candidate's word set
- Example: `Pioneer Credit Solutions Pty Ltd` matches `Pioneer Credit`

### Not applied
- No alias/mapping table
- No fuzzy/Levenshtein matching
- No abbreviation expansion (CBA ≠ Commonwealth Bank of Australia)

## 4. Root Cause of All Failures

**The Axion `clients` table contains 0 rows.** Every `_match_client()` call returns `None`
because there are no candidates to match against. The importer never creates clients — it only
matches against existing records.

## 5. Failure Categorisation (15,587 records)

| Category | Count | % | First Client Field | Failure Reason |
|----------|------:|---:|-------------------|----------------|
| Parser extracted client name | 5980 | 38.4% | `parsed_client_name` | Would resolve IF clients table populated; currently returns NULL because clients table is empty |
| No parsed name, Company present | 3228 | 20.7% | `Company` | Company field = borrower's company (not lender). Fallback match attempted but (a) table empty, (b) value is customer name, not lender |
| Neither parsed name nor Company | 6379 | 40.9% | (none) | No client-related source data available. Description starts with regulation type or is empty |

### 5a. Sub-categories for records with no parsed_client_name

| Sub-category | Count | Description |
|-------------|------:|-------------|
| starts_with_regulation_type | 6190 | Description begins with `Regulated`/`Unregulated` — no client name prefix to parse |
| unstructured_text | 2266 | Free-text with no recognisable client name pattern |
| field_call_only | 1068 | `Field Call - See instructions` with no embedded lender name |
| no_description | 83 | Empty description field |

## 6. Proposed Client List (seed the `clients` table)

These are the unique normalised client names from the parser, ranked by frequency.
Creating these as Axion clients would immediately resolve **all** Category 1 failures.

| # | Canonical Name | Normalised Key | Variants | Job Count |
|---|---------------|---------------|----------|---------:|
| 1 | Allied | `allied` | Allied finance, Allied Finance, Allied  finance, Allied  Finance | 466 |
| 2 | VWFS | `vwfs` | — | 320 |
| 3 | Angle finance | `angle` | Angle Finance, Angle  finance, Angle  Finance, ANGLE FINANCE, Angle | 230 |
| 4 | Westpac | `westpac` | — | 228 |
| 5 | TURO | `turo` | Turo | 195 |
| 6 | Pepper Money Limited | `pepper money` | Pepper Money, Pepper money, Pepper money: | 194 |
| 7 | Macquarie Leasing Pty Ltd | `macquarie` | Macquarie Leasing, Macquarie, MACQUARIE LEASING | 182 |
| 8 | Capital Finance | `capital` | Capital  finance, Capital finance, Capital  Finance, Capital | 152 |
| 9 | Toyota | `toyota` | Toyota Finance, Toyota finance | 152 |
| 10 | CBA | `cba` | CBA: | 113 |
| 11 | Moneyme | `moneyme` | MoneyMe | 111 |
| 12 | Pickles | `pickles` | Pickles finance, . Pickles | 110 |
| 13 | BOQ | `boq` | Boq | 90 |
| 14 | NCML | `ncml` | — | 84 |
| 15 | Flexicommercial | `flexicommercial` | flexicommercial, FLEXICOMMERCIAL, FLEXICOMMERCIAL PTY LTD, Flexicommercial Pty Ltd | 77 |
| 16 | Pioneer Credit Solutions Pty Ltd | `pioneer credit solutions` | Pioneer Credit Solutions | 71 |
| 17 | Now Finance | `now` | Now finance, Now  finance | 68 |
| 18 | Harmoney | `harmoney` | — | 66 |
| 19 | PowerTorque | `powertorque` | PowerTorque Finance | 63 |
| 20 | Swoosh | `swoosh` | SWOOSH, Swoosh Finance | 63 |
| 21 | Mercedes | `mercedes` | — | 59 |
| 22 | NAB | `nab` | Nab | 57 |
| 23 | Rapid Loans | `rapid loans` | Rapid Loans:, Rapid Loans., Rapid Loans Pty Ltd | 54 |
| 24 | Firstmac | `firstmac` | — | 48 |
| 25 | Process Serve | `process serve` | Process serve | 45 |
| 26 | Volkswagen Financial | `volkswagen financial` | Volkswagen Financial:, Volkswagen financial | 43 |
| 27 | BMW | `bmw` | — | 42 |
| 28 | Volkswagen Financial Service | `volkswagen financial service` | — | 41 |
| 29 | Liberty | `liberty` | Liberty Finance, Liberty: | 41 |
| 30 | Yamaha Motor Finance | `yamaha motor` | — | 40 |
| 31 | ACM | `acm` | — | 38 |
| 32 | Credit Corp Group | `credit corp group` | — | 33 |
| 33 | CH UAL | `ch ual` | CH  UAL | 32 |
| 34 | Toyota Finance Australia | `toyota finance australia` | — | 31 |
| 35 | ST  George | `st george` | St George, St George. | 30 |
| 36 | Latitude | `latitude` | — | 30 |
| 37 | Pickles account | `pickles account` | Pickles  account | 29 |
| 38 | Allied Retail Finance | `allied retail` | — | 28 |
| 39 | Finance One | `finance one` | FINANCE ONE, Finance one, Finance  One | 27 |
| 40 | Jacaranda Finance | `jacaranda` | Jacaranda | 26 |
| 41 | WISE | `wise` | Wise | 26 |
| 42 | Australian Motorcycle Marine Finance | `australian motorcycle marine` | Australian Motorcycle & Marine Finance | 25 |
| 43 | Flexicommerical | `flexicommerical` | flexicommerical | 25 |
| 44 | GLA | `gla` | GLA:, GLA. | 25 |
| 45 | Slattery Auctions | `slattery auctions` | — | 23 |
| 46 | Resimac | `resimac` | — | 21 |
| 47 | Difrent Rental | `difrent rental` | Difrent Rental Pty Ltd | 21 |
| 48 | Collection House on behalf of St George | `collection house on behalf of st george` | — | 21 |
| 49 | Shift | `shift` | — | 20 |
| 50 | Pioneer Credit | `pioneer credit` | Pioneer credit | 20 |
| 51 | AUSRN | `ausrn` | Ausrn | 20 |
| 52 | Automotive Finance | `automotive` | Automotive finance | 19 |
| 53 | Allied Credit: | `allied credit` | Allied Credit | 19 |
| 54 | Right Road Finance | `right road` | — | 18 |
| 55 | Flexfleet | `flexfleet` | FlexFleet | 17 |
| 56 | Moneytech | `moneytech` | — | 17 |
| 57 | Orix | `orix` | ORIX | 17 |
| 58 | Slattery's | `slatterys` | Slatterys | 17 |
| 59 | Polygon | `polygon` | — | 16 |
| 60 | RAA Insurance | `raa insurance` | RAA INSURANCE | 15 |
| 61 | BMW CHATTEL MORTGAGE | `bmw chattel mortgage` | BMW CHATTEL MORTGAGE: | 15 |
| 62 | AAMI | `aami` | — | 15 |
| 63 | Liberty File | `liberty file` | Liberty file | 14 |
| 64 | Dealer Motor Finance Australia | `dealer motor finance australia` | — | 13 |
| 65 | Bank of Melbourne | `bank of melbourne` | Bank of  Melbourne, Bank Of Melbourne | 13 |
| 66 | Selfco | `selfco` | Selfco leasing, Selfco Leasing | 12 |
| 67 | SCOTPAC | `scotpac` | ScotPac | 12 |
| 68 | Plenti  Finance | `plenti` | Plenti, Plenti Finance | 12 |
| 69 | Repo/Coll | `repocoll` | — | 12 |
| 70 | PFM Mortgage | `pfm mortgage` | — | 12 |
| 71 | Scottish Pacific | `scottish pacific` | Scottish pacific | 11 |
| 72 | Slatterys account | `slatterys account` | — | 10 |
| 73 | REPO | `repo` | Repo | 10 |
| 74 | Pepper Auto Finance | `pepper auto` | — | 10 |
| 75 | 2 of 2. | `2 of 2` | 2 of 2 | 10 |
| 76 | Commonwealth Bank of Australia | `commonwealth bank of australia` | Commonwealth Bank of Australia: | 9 |
| 77 | Azora | `azora` | AZORA | 9 |
| 78 | Paccar Financial | `paccar financial` | — | 9 |
| 79 | Scania Finance | `scania` | Scania | 9 |
| 80 | ARG | `arg` | — | 9 |
| ... | _1086 more with count < 9_ | | | |

## 7. Alias Mappings Needed

The normalisation already collapses most variants (e.g., `Allied Finance` → `allied` ← `Allied finance`).
However, these cases require explicit alias entries:

| Alias / Variant | Should Map To | Reason |
|----------------|--------------|--------|
| `VWFS` | `Volkswagen Financial Services` | Abbreviation — normalisation cannot expand |
| `VW`, `VW Finance` | `Volkswagen Financial Services` | Short form |
| `CBA` | `Commonwealth Bank of Australia` | Abbreviation |
| `NAB` | `National Australia Bank` | Abbreviation |
| `BOQ` | `Bank of Queensland` | Abbreviation |
| `ACM` | `ACM Group` | Abbreviation |
| `NCML` | `NCML Group` | Abbreviation |
| `BMW` | `BMW Financial Services` | Short form |
| `TURO` | `Turo Finance` | Variant casing |
| `Moneyme` / `MoneyMe` | `MoneyMe` | Case variant |
| `Get Capital` | `Get Capital Finance` | Suffix stripped too aggressively |
| `St George` / `ST George` | `St George Bank` | Missing bank suffix |

## 8. Proposed Fix (3-step)

### Step A: Populate clients table
Create Axion client records for each unique normalised group above.
This alone resolves **5,980** of 15,587 jobs (38.4%).

### Step B: Add client_aliases table
```sql
CREATE TABLE client_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    alias TEXT NOT NULL COLLATE NOCASE,
    UNIQUE(alias)
);
```
Update `_match_client()` to check aliases after Tier 1 (exact) and before Tier 2 (normalised).

### Step C: Run backfill
After Steps A and B, execute `backfill_client_links()` from the Admin UI.
This re-parses all imported job descriptions and matches against the now-populated clients table.
Progress is tracked live via the Client Backfill card on `/admin/geoop-import`.

## 9. False Positive Parser Fix Applied

Added to `_BAD_CLIENT_KW` reject list: `repo only`, `instructions`, `see instructions`,
`client manager`, `deliver to`, `note`, `must`, `call`, `payout`, `turo res id`, `res id`.
This eliminates **164** records that were incorrectly tagged as parsed client names.

## 10. Company Field Assessment

The `Company` CSV column contains the **borrower's company** (debtor), not the lending client.
Examples: `DOSA PALACE`, `INDOPAK LOGISTICS PTY LTD`, `CUT DIG N LOAD PTY LTD`.
This field is used as a fallback in `_match_client()`, but it will virtually never match
a lender name. It is, however, correctly mapped to the Axion customer record during import.
**Recommendation:** Do not rely on Company for client (lender) resolution.

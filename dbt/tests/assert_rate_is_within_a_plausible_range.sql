/*
    Range check, in the sense of section 36 of the brief.

    not_null catches a value that failed to parse. It does NOT catch a value
    that parses perfectly and is absurd -- a decimal point in the wrong place
    turns 2.25 into 225, and every other test stays green.

    Bounds and why they are these ones:
      lower 0  : Canada has never had a negative policy rate. If that ever
                 changes, this test failing is the CORRECT outcome: it forces a
                 deliberate decision instead of silently accepting the value.
      upper 25 : the highest Bank of Canada policy rate on record is 20.03 %
                 in August 1981, well before this project window. 25 leaves
                 room without accepting nonsense.
*/

select
    series_id,
    observation_date,
    rate_percent,
    value_raw

from {{ ref('stg_bank_of_canada__interest_rates') }}

where rate_percent < 0
   or rate_percent > 25

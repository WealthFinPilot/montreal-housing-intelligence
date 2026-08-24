{#
    Statistics Canada never leaves a cell blank when it has nothing to publish.
    It prints a symbol beside the value, and the symbols are not synonyms.

    Read verbatim from the legend inside 98100058_MetaData.csv:

        ''     the value beside it is published
        'x'    "suppressed to meet the confidentiality requirements of the
               Statistics Act" -- a real number exists, the law forbids
               printing it, and it is almost always a small-count geography
        '...'  "not applicable" -- the question does not arise for this
               combination of household size and household type

    AND THE TWO PLACEHOLDERS ARE NOT THE SAME PLACEHOLDER

    Measured over the Montréal metropolitan area on 2026-08-24, for the two
    2020 income measures:

        symbol ''     -> a real number      99 282 cells
        symbol '...'  -> the literal '0'    36 808 cells
        symbol 'x'    -> empty              18 680 cells

    A "not applicable" cell prints a ZERO, not a blank. Read without its
    symbol, it is a median household income of nought dollars -- a number that
    casts cleanly, averages quietly, and is wrong 36 808 times. That is why
    statcan_value below keys on the symbol and never on the value being empty.

    These two macros exist so the mapping is written once instead of twelve
    times. Six measures, each needing a value and a status: hand-writing all
    twelve is how eleven end up right and one ends up reading the neighbouring
    column, which is a mistake no test would notice because the number would
    still be a plausible income.

    Anything else that ever appears becomes 'unknown_symbol', which an
    accepted_values test turns into a failed build rather than a silent NULL.
#}

{% macro statcan_status(symbol_column) %}
    case trim({{ symbol_column }})
        when ''    then 'published'
        when 'x'   then 'suppressed'
        when '...' then 'not_applicable'
        else            'unknown_symbol'
    end
{% endmacro %}


{% macro statcan_value(value_column, symbol_column) %}
    {#
        A number only when the source says it published one. A suppressed cell
        and an inapplicable cell both become NULL here -- they are not numbers
        -- but the status column beside this one keeps them distinguishable,
        which is the whole point. Never fill either with a zero, a neighbour's
        value or an interpolation: brief section 41, principle 1.
    #}
    case
        when trim({{ symbol_column }}) = ''
        then nullif(trim({{ value_column }}), '')::numeric
    end
{% endmacro %}

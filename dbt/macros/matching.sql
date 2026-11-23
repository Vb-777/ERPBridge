{# ---------- Portable text normalisation for master-data matching (DuckDB and Snowflake). ---------- #}

{# lower-case, strip punctuation to spaces, collapse whitespace, pad with spaces so token replaces are word-safe #}
{% macro mdm_clean(expr) -%}
    (' ' || trim({{ re_replace_all(re_replace_all("lower(coalesce(" ~ expr ~ ", ''))", "'[^a-z0-9äöüßàâçéèêëîïôûùÿ]+'", "' '"), "' +'", "' '") }}) || ' ')
{%- endmacro %}

{# "SMITH, John" -> "John SMITH"; anything else unchanged #}
{% macro mdm_person_order(expr) -%}
    case when position(',' in {{ expr }}) > 0
         then trim(split_part({{ expr }}, ',', 2)) || ' ' || trim(split_part({{ expr }}, ',', 1))
         else {{ expr }} end
{%- endmacro %}

{% macro mdm_company(expr) -%}
    trim(
    {%- set rules = [(' incorporated ', ' inc '), (' corporation ', ' corp '), (' company ', ' co '),
                     (' limited ', ' ltd '), (' and ', ' '), (' the ', ' ')] -%}
    {%- set ns = namespace(x=mdm_clean(expr)) -%}
    {%- for a, b in rules -%}{%- set ns.x = "replace(" ~ ns.x ~ ", '" ~ a ~ "', '" ~ b ~ "')" -%}{%- endfor -%}
    {{ ns.x }})
{%- endmacro %}

{% macro mdm_address(expr) -%}
    trim(
    {%- set rules = [(' street ', ' st '), (' avenue ', ' ave '), (' drive ', ' dr '), (' road ', ' rd '),
                     (' lane ', ' ln '), (' court ', ' ct '), (' boulevard ', ' blvd '), (' place ', ' pl '),
                     (' way ', ' wy '), (' circle ', ' cir '), ('straße ', 'str '), ('strasse ', 'str '),
                     (' r ', ' rue ')] -%}
    {%- set ns = namespace(x=mdm_clean(expr)) -%}
    {%- for a, b in rules -%}{%- set ns.x = "replace(" ~ ns.x ~ ", '" ~ a ~ "', '" ~ b ~ "')" -%}{%- endfor -%}
    {{ ns.x }})
{%- endmacro %}

{% macro mdm_postal(expr) -%}
    lower(replace(coalesce({{ expr }}, ''), ' ', ''))
{%- endmacro %}

{% macro mdm_phone_tail(expr) -%}
    right({{ re_replace_all("coalesce(" ~ expr ~ ", '')", "'[^0-9]'", "''") }}, 7)
{%- endmacro %}

{# ---------- Jaro-Winkler similarity in [0, 1], dispatched per warehouse. ---------- #}
{% macro jaro_winkler(a, b) -%}{%- if adapter is defined -%}{{ return(adapter.dispatch('jaro_winkler')(a, b)) }}{%- else -%}{{ default__jaro_winkler(a, b) }}{%- endif -%}{%- endmacro %}
{% macro default__jaro_winkler(a, b) -%}jaro_winkler_similarity({{ a }}, {{ b }}){%- endmacro %}
{% macro snowflake__jaro_winkler(a, b) -%}(jarowinkler_similarity({{ a }}, {{ b }}) / 100.0){%- endmacro %}

{# ---------- Replace every regex match: DuckDB needs the 'g' flag, Snowflake replaces all by default. ---------- #}
{% macro re_replace_all(x, pattern, repl) -%}{%- if adapter is defined -%}{{ return(adapter.dispatch('re_replace_all')(x, pattern, repl)) }}{%- else -%}{{ default__re_replace_all(x, pattern, repl) }}{%- endif -%}{%- endmacro %}
{% macro default__re_replace_all(x, pattern, repl) -%}regexp_replace({{ x }}, {{ pattern }}, {{ repl }}, 'g'){%- endmacro %}
{% macro snowflake__re_replace_all(x, pattern, repl) -%}regexp_replace({{ x }}, {{ pattern }}, {{ repl }}){%- endmacro %}

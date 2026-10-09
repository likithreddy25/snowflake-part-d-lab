-- Generic test to ensure numeric columns have positive values (or zero)
{% test positive_values(model, column_name) %}

SELECT *
FROM {{ model }}
WHERE {{ column_name }} < 0

{% endtest %}

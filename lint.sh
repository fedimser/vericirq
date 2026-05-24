result=0

echo "Running black..."
black --check ./vericirq
result+=$?

echo "Running mypy..."
mypy ./vericirq
result+=$?

exit $result
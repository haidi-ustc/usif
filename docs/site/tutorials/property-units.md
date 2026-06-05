# Property Units

```python
props.set_tensor("quadrupole", tensor, units="Ang^2")
assert props.get_units("quadrupole") == "Å^2"
```

USIF normalizes common Unicode and ASCII aliases but does not convert numeric values between units. See `examples/08_property_units.py`.

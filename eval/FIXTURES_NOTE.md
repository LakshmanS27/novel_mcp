# Note on planted secrets

Files seeded by `seed_ground_truth.py` intentionally contain **synthetic,
non-functional secrets**: canonical documentation examples (AWS docs-style
keys marked EXAMPLE4EVAL, Stripe's public documentation key body), Luhn-valid
test card numbers, and fabricated PII on the reserved-style `example.corp`
domain. Signature-matching tokens are split across adjacent string literals in
the source so hosting-platform push protection does not block commits; Python
rejoins them at parse time, so fixtures written to disk are byte-identical to
the unsplit form.

Any scanner flagging this repository is working as intended — and is,
incidentally, demonstrating the context-blindness this project addresses.

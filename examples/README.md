# Examples

From a source checkout, install the package first with `python -m pip install -e .`; an installed
wheel needs no extra setup.

`forge-mutation/` models a Forge controller proposing its own production-router change while also
shortening the observation window from 24 hours to 30 minutes. The predecessor charter, candidate
charter, and proposal are separate digest-bound artifacts. Polyhorizon therefore requests evidence,
recourse reservation, predecessor-standing ratification, and explicit releases for the changed
purpose, horizon, and obligation instead of letting the Forge score ratify itself.

Run the in-process demonstration:

```console
python examples/python/forge_mutation.py
```

Run the dependency-free Node client against the Python NDJSON sidecar:

```console
node examples/node/sidecar-client.mjs python
```

The Node script accepts the Python executable as its first argument, so virtual environments and
Windows paths do not require shell quoting inside the client.

`conformance/digests.json` fixes the canonical JSON and domain-separated digest profile. Ports in
other languages should run that corpus before exchanging effect receipts or session state.

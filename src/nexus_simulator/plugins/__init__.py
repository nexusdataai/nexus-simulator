"""Built-in simulator plugins.

Each plugin is self-contained under ``plugins/<name>/`` and is wired into a
``SimulatorRegistry`` by ``build_simulator`` only when its corresponding
``SimulatorConfig`` field is non-``None``.

Plugins land per phase:

- ``wxcc``            (Phase 5)
- ``sfdc``            (Phase 6)
- ``oracle_erp``      (Phase 7)
- ``sap``             (Phase 7)
- ``external_source`` (Phase 8)
"""

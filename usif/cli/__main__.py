"""``python -m usif.cli`` runs the ``usif`` command."""

from usif.cli.root import main

raise SystemExit(main())  # pragma: no cover - the console script covers main()

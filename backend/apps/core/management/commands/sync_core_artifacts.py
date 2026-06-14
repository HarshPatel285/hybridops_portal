import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.services.core_sync import sync_core_artifacts


class Command(BaseCommand):
    help = "Synchronize finalized hybridops_core artifacts into PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--artifacts-dir",
            default=os.getenv("HYBRIDOPS_CORE_ARTIFACTS_DIR", "/core/artifacts"),
        )
        parser.add_argument("--if-present", action="store_true")

    def handle(self, *args, **options):
        artifact_dir = Path(options["artifacts_dir"]).expanduser().resolve()
        if not artifact_dir.exists() and options["if_present"]:
            self.stdout.write(self.style.WARNING(f"Core artifacts not mounted: {artifact_dir}"))
            return
        try:
            summary = sync_core_artifacts(artifact_dir)
        except (FileNotFoundError, ValueError, KeyError) as exc:
            if options["if_present"]:
                self.stdout.write(self.style.WARNING(str(exc)))
                return
            raise CommandError(str(exc)) from exc
        for key, value in summary.items():
            self.stdout.write(f"{key}: {value}")
        self.stdout.write(self.style.SUCCESS("Finalized HybridOps core artifacts synchronized."))

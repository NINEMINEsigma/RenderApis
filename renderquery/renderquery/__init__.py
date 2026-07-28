"""RenderQuery — Database-like query engine for RenderDoc replay snapshots."""

__version__ = "0.1.0"

# Lightweight modules that don't require the renderdoc SWIG binding.
# These are safe to import without a built RenderDoc environment.
from .engine.plan import QueryPlan, Step, Projection, SourceSpec
from .engine.artifacts import ArtifactSpec
from .engine.dsl import Query

# Heavier modules that require the renderdoc SWIG binding.
# Import these explicitly: from renderquery.engine.executor import Executor
# from renderquery.engine.catalog import Catalog
# from renderquery.sdk import RenderQueryClient
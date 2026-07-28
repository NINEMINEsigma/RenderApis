"""Engine: catalog, query plan IR, DSL, executor, artifacts."""

# Lightweight — no renderdoc dependency
from .plan import QueryPlan, Step, Projection, SourceSpec
from .artifacts import ArtifactSpec
from .dsl import Query

# Heavy — requires renderdoc SWIG binding, import explicitly:
# from .catalog import Catalog
# from .executor import Executor, ExecutorBusy
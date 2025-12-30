import os

import truststore
import truststore._api as tapi
from hatchet_client import hatchet
from worker_config import HatchetWorkerType
from workflows.auth0_sync_workflow import (
    auth0_sync_task,
    process_auth0_event_task,
    scheduled_auth0_sync_task,
)
from workflows.autodocs_functions import llm_generate_task
from workflows.autodocs_workflow import autodocs_task
from workflows.deep_context_functions import make_changelog_task
from workflows.inspector_functions import (
    codebase_tags_task,
    deep_context_docs_task,
    export_tech_docs_task,
    folder_doc_task,
    symbol_doc_task,
    tech_doc_task,
    toplevel_doc_task,
)
from workflows.inspector_workflow import inspector_task
from workflows.analytics_workflow import analytics_task
from workflows.onboarding_workflows import (
    connect_repos_for_installation_task,
    handle_azure_devops_events_task,
    handle_bitbucket_events_task,
    handle_github_events_task,
    handle_gitlab_events_task,
    run_codebase_connection_task,
)
from workflows.pdf_processing_workflow import pdf_processing_task

truststore.inject_into_ssl()
# Patch botocore to use truststore's SSLContext (see https://github.com/sethmlarson/truststore/pull/180)
try:
    import botocore.httpsession

    botocore.httpsession.SSLContext = tapi.SSLContext
except ImportError:
    pass

heavy_workflow_set = [
    pdf_processing_task,
    inspector_task,
    analytics_task,
    tech_doc_task,
    folder_doc_task,
    symbol_doc_task,
    toplevel_doc_task,
    autodocs_task,
    run_codebase_connection_task,
    llm_generate_task,
    make_changelog_task,
    deep_context_docs_task,
    export_tech_docs_task,
    codebase_tags_task,
]

base_workflow_set = [
    auth0_sync_task,
    process_auth0_event_task,
    scheduled_auth0_sync_task,
    handle_github_events_task,
    handle_azure_devops_events_task,
    handle_bitbucket_events_task,
    handle_gitlab_events_task,
    connect_repos_for_installation_task,
]


def main() -> None:
    worker_type = HatchetWorkerType(os.environ["WORKFLOW_SET_NAME"])
    workflows = (
        heavy_workflow_set
        if worker_type == HatchetWorkerType.HEAVY
        else base_workflow_set
    )
    worker = hatchet.worker(
        f"{worker_type}-worker",
        slots=250,
        workflows=workflows,
    )
    worker.start()


if __name__ == "__main__":
    main()

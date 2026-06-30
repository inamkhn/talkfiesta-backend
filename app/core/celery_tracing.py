import logging
from celery.signals import before_task_publish, task_prerun, task_postrun
from asgi_correlation_id import correlation_id

logger = logging.getLogger(__name__)


@before_task_publish.connect
def before_task_publish_handler(headers=None, **kwargs):
    """
    Inject current HTTP correlation ID into Celery task headers prior to publish.
    """
    if headers:
        cid = correlation_id.get()
        if cid:
            headers["x_correlation_id"] = cid


@task_prerun.connect
def task_prerun_handler(task=None, **kwargs):
    """
    Before running task in Celery worker, restore correlation ID to context from headers.
    """
    if task and task.request and task.request.headers:
        cid = task.request.headers.get("x_correlation_id")
        if cid:
            correlation_id.set(cid)
            logger.debug(f"Restored correlation_id {cid} context to Celery worker.")


@task_postrun.connect
def task_postrun_handler(**kwargs):
    """
    Clean up correlation ID context after task execution.
    """
    correlation_id.set(None)

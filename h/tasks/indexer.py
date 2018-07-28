# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from h import models, storage
from h.celery import celery, get_task_logger
from h.search.index import BatchIndexer, delete, index

log = get_task_logger(__name__)


@celery.task
def add_annotation(id_):
    annotation = storage.fetch_annotation(celery.request.db, id_)
    if annotation:
        index(celery.request.es6, annotation, celery.request)

        # If a reindex is running at the moment, add annotation to the new index
        # as well.
        future_es6_index = _current_reindex_new_name(celery.request, 'reindex.new_es6_index')
        if future_es6_index is not None:
            index(celery.request.es6, annotation, celery.request,
                  target_index=future_es6_index)

        if annotation.is_reply:
            add_annotation.delay(annotation.thread_root_id)


@celery.task
def delete_annotation(id_):
    delete(celery.request.es6, id_)

    # If a reindex is running at the moment, delete annotation from the
    # new index as well.
    future_es6_index = _current_reindex_new_name(celery.request, 'reindex.new_es6_index')
    if future_es6_index is not None:
        delete(celery.request.es6, id_, target_index=future_es6_index)


@celery.task
def reindex_user_annotations(userid):
    ids = [a.id for a in celery.request.db.query(models.Annotation.id).filter_by(userid=userid)]

    indexer = BatchIndexer(celery.request.db, celery.request.es6, celery.request)
    errored = indexer.index(ids)
    if errored:
        log.warning('Failed to re-index annotations into ES6 %s', errored)


def _current_reindex_new_name(request, new_index_setting_name):
    settings = celery.request.find_service(name='settings')
    new_index = settings.get(new_index_setting_name)

    return new_index

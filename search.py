from app import app, db, models

def add_to_index(index, model):
    if not app.elasticsearch:
        return
    payload={}
    for field in model.__searchable__:
        payload[field] = getattr(model,field)
    app.elasticsearch.index(index=index, doc_type=index, id=model.id, body=payload)

def remove_from_index(index, model):
    if not app.elasticsearch:
        return
    app.elasticsearch.delete(index=index, doc_type=index, id=model.id)

def query_index(index, query, page, per_page):
    if not app.elasticsearch:
        return [], 0
    print(page, per_page,(page-1)*per_page)
    search = app.elasticsearch.search(
        index=index, doc_type=index,
        body = {
            'query':{
                'multi_match':{
                    'query':query,
                    'fields':['body']
                }
            },
            'from':(page-1)*per_page,
            'size':per_page
        }
    )
    ids = [int(hit['_id']) for hit in search['hits']['hits']]
    return ids, search['hits']['total']

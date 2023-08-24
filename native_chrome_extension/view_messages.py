import html
import json
import sqlite3

from nicegui import ui

conn = sqlite3.connect("messages.db")
c = conn.cursor()

c.execute("SELECT * FROM messages")
messages = c.fetchall()

conn.close()

dicts = []
trees = []

# 28 : dict_keys(['action', 'documentBody', 'documentHead', 'url'])


for msg in messages:
    dicts.append({"id": msg[0], "message": json.loads(msg[1])})

for d in dicts:
    tree = [{"id": "id: " + f'{d["id"]} : url: {d["message"]["url"]}'}]
    children = []

    children.append({"id": "action", "children": [{"id": str(d["message"]["action"])}]})

    if d["message"]["action"] == "captureDocumentState":
        document_body = html.escape(d["message"]["documentBody"])
        children.append(
            {
                "id": "documentBody",
                "children": [{"id": "<pre>" + document_body + "</pre>"}],
            }
        )
        document_head = html.escape(d["message"]["documentHead"])
    else:
        tagName = d["message"]["tagName"]
        children.append({"id": "tagName", "children": [{"id": str(tagName)}]})

        attributes = d["message"]["attributes"]
        children.append({"id": "attributes", "children": [{"id": str(attributes)}]})
    children.append(
        {"id": "documentHead", "children": [{"id": "<pre>" + document_head + "</pre>"}]}
    )
    children.append({"id": "url", "children": [{"id": str(d["message"]["url"])}]})
    tree[0]["children"] = children
    ui.tree(tree, label_key="id")._props["default-expand-all"] = True

ui.run(port=7777)

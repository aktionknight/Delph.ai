with open('apps/api/app/api/routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

delete_brand_code = """    @app.delete("/brands/{brand_id}")
    def delete_brand(brand_id: str, db: Session = Depends(session)):
        b = get(db, brand_id, "brand")
        campaigns = [c for c in db.list("campaign") if c.parent_id == brand_id or c.data.get("brand_id") == brand_id]
        for c in campaigns:
            for a in db.list("asset", c.id):
                db.delete(a)
            db.delete(c)
        db.delete(b)
        db.commit()
        return {"ok": True, "id": brand_id}

    @app.patch("/brands/{brand_id}")"""

content = content.replace("""    @app.patch("/brands/{brand_id}")""", delete_brand_code, 1)

delete_campaign_code = """    @app.delete("/campaigns/{campaign_id}")
    def delete_campaign(campaign_id: str, db: Session = Depends(session)):
        c = get(db, campaign_id, "campaign")
        for a in db.list("asset", c.id):
            db.delete(a)
        db.delete(c)
        db.commit()
        return {"ok": True, "id": campaign_id}

    @app.post("/campaigns/{campaign_id}/reviews")"""

content = content.replace("""    @app.post("/campaigns/{campaign_id}/reviews")""", delete_campaign_code, 1)

delete_asset_code = """    @app.delete("/assets/{asset_id}")
    def delete_asset(asset_id: str, db: Session = Depends(session)):
        a = get(db, asset_id, "asset")
        c = get(db, a.parent_id, "campaign")
        db.delete(a)
        data = campaign_state(db, c)
        save(db, c, data)
        return {"ok": True, "id": asset_id}

    @app.post("/campaigns/{campaign_id}/experiments")"""

content = content.replace("""    @app.post("/campaigns/{campaign_id}/experiments")""", delete_asset_code, 1)

with open('apps/api/app/api/routes.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated routes.py with delete endpoints')

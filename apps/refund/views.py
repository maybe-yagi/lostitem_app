import os
from datetime import datetime
from pathlib import Path

from flask import (Blueprint, redirect, render_template, request, session,
                   url_for)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from sqlalchemy import extract, func

from apps.app import db
from apps.refund.forms import (PoliceRefundForm, RefundedForm, RefundForm,
                               RefundItemForm, RefundList, RegisterItem)
from apps.register.models import Denomination, LostItem

refund = Blueprint(
    "refund",
    __name__,
    template_folder="templates",
    static_folder="static",
)

basedir = Path(__file__).parent.parent
UPLOAD_FOLDER = str(Path(basedir, "PDFfile", "refund_list_pdf"))


# 届出受理番号登録
@refund.route("/register_num", methods=["POST", "GET"])
def register_num():
    form = RegisterItem()
    all_lost_item = db.session.query(LostItem).all()

    if form.submit.data:
        start_date = form.start_date.data
        end_date = form.end_date.data
        finder_choice = form.finder_choice.data
        waiver = form.waiver.data
        # クエリの生成
        query = db.session.query(LostItem)
        if start_date and end_date:
            query = query.filter(LostItem.get_item.between(start_date, end_date))
        elif start_date:
            query = query.filter(LostItem.get_item >= start_date)
        elif end_date:
            query = query.filter(LostItem.get_item <= end_date)
        if finder_choice == "占有者拾得":
            query = query.filter(LostItem.choice_finder == "占有者拾得")
        elif finder_choice == "第三者拾得":
            query = query.filter(LostItem.choice_finder == "第三者拾得")
        if waiver == "権利行使":
            query = query.filter(LostItem.own_waiver == "放棄しない")
        elif waiver == "権利放棄":
            query = query.filter(LostItem.own_waiver == "一切放棄")
        search_results = query.all()
        session['search_results'] = [item.to_dict() for item in search_results]
        return redirect(url_for("refund.search"))

    return render_template("refund/index.html", all_lost_item=all_lost_item, form=form)


# 検索結果
@refund.route("/search", methods=["POST", "GET"])
def search():
    search_results = session.get('search_results', [])
    form = RefundForm()
    if form.submit.data:
        item_ids = request.form.getlist('item_ids')
        session['item_ids'] = item_ids
        items = db.session.query(LostItem).filter(LostItem.id.in_(item_ids)).all()
        for item in items:
            item.receiptnumber = form.receiptnumber.data
            item.refund_expect = form.refund_expect.data
            if form.refund_expect:
                item.refund_situation = "還付予定"
            else:
                item.refund_situation = ""
        db.session.commit()
        return redirect(url_for("refund.register_num"))
    return render_template("refund/search.html", search_results=search_results,
                           form=form)


# 還付番号処理
@refund.route("/refund_item", methods=["POST", "GET"])
def refund_item():
    form = RefundItemForm()
    all_lostitem = db.session.query(LostItem).all()

    if form.submit.data:
        start_date = form.start_date.data
        end_date = form.end_date.data
        receiptnumber = form.receiptnumber.data
        refund_expect = form.refund_expect.data
        returned = form.returned.data
        item_plice = form.item_plice.data
        item_feature = form.item_feature.data
        # クエリの生成
        query = db.session.query(LostItem)
        if start_date and end_date:
            query = query.filter(LostItem.get_item.between(start_date, end_date))
        elif start_date:
            query = query.filter(LostItem.get_item >= start_date)
        elif end_date:
            query = query.filter(LostItem.get_item <= end_date)
        if receiptnumber:
            query = query.filter(LostItem.receiptnumber == receiptnumber)
        if refund_expect:
            query = query.filter(func.date(LostItem.refund_expect) == refund_expect)
        if not returned:
            query = query.filter(LostItem.refund_situation == "還付予定")
        if item_plice:
            query = query.filter(LostItem.item_value is True)
        if item_feature:
            query = query.filter(LostItem.item_feature.ilike(f"%{item_feature}%"))
        search_results = query.all()
        print(refund_expect)
        session['search_results'] = [item.to_dict() for item in search_results]
        return redirect(url_for("refund.refund_item_search"))
    return render_template("refund/refund_item.html",
                           form=form, all_lostitem=all_lostitem)


# 還付処理、検索結果
@refund.route("/refund_item_search", methods=["POST", "GET"])
def refund_item_search():
    search_results = session.get('search_results', [])
    form = PoliceRefundForm()

    if form.submit.data:
        item_ids = request.form.getlist('item_ids')
        session['item_ids'] = item_ids
        police_item_ids = request.form.getlist('police_item_ids')
        session['police_item_ids'] = police_item_ids
        items = db.session.query(LostItem).filter(LostItem.id.in_(item_ids)).all()
        police_items = (
            db.session.query(LostItem)
            .filter(LostItem.id.in_(police_item_ids)).all()
            )
        for item in items:
            item.refund_situation = "還付済"
            item.refund_date = form.refund_date.data
            item.refund_manager = form.refund_manager.data
        db.session.commit()
        for item in police_items:
            item.refund_date = form.refund_date.data
            item.refund_manager = form.refund_manager.data
            item.refund_situation = "対応済"
        db.session.commit()
        return redirect(url_for("refund.refund_item"))
    return render_template("refund/refund_item_search.html",
                           search_results=search_results, form=form)


# 還付済物件処理
@refund.route("/refunded", methods=["POST", "GET"])
def refunded():
    form = RefundedForm()
    search_results = session.get('search_results', None)
    if search_results is None:
        search_results = db.session.query(LostItem).all()

    if form.submit.data:
        start_date = form.start_date.data
        end_date = form.end_date.data
        refund_date = form.refund_date.data
        police_date = form.police_date.data
        refunded_process = form.refunded_process.data
        refunded_bool = form.refunded_bool.data
        # クエリの生成
        query = db.session.query(LostItem)
        if start_date and end_date:
            query = query.filter(LostItem.get_item.between(start_date, end_date))
        elif start_date:
            query = query.filter(LostItem.get_item >= start_date)
        elif end_date:
            query = query.filter(LostItem.get_item <= end_date)
        if refund_date:
            query = query.filter(func.date(LostItem.refund_date) == refund_date)
        if police_date:
            query = query.filter(LostItem.police_date == police_date)
        if refunded_process != '':
            query = query.filter(LostItem.refunded_process == refunded_process)
        if not refunded_bool:
            query = query.filter(LostItem.refund_situation != "処理済")
        search_results = query.all()
        session['search_results'] = [item.to_dict() for item in search_results]
        return redirect(url_for("refund.refunded"))
    if form.submit2.data:
        item_ids = request.form.getlist('item_ids')
        items = db.session.query(LostItem).filter(LostItem.id.in_(item_ids)).all()
        for item in items:
            select_value = request.form.get(f'item_select_{item.id}')
            item.refunded_process = select_value
        db.session.commit()
        return redirect(url_for('refund.refunded'))
    if form.submit3.data:
        item_ids = request.form.getlist('item_ids')
        items = db.session.query(LostItem).filter(LostItem.id.in_(item_ids)).all()
        make_refunded_list(items)
        return redirect(url_for('refund.refunded'))
    return render_template("refund/refunded.html", form=form,
                           search_results=search_results)


# 還付請求一覧
@refund.route("/refund_list", methods=["POST", "GET"])
def refund_list():
    all_lost_item = db.session.query(LostItem).all()
    form = RefundList()
    if form.submit.data:
        refund_expect_year = form.refund_expect_year.data
        refund_situation = form.refund_situation.data
        # クエリの生成
        query = db.session.query(LostItem)
        if refund_expect_year:
            query = query.filter(extract('year', LostItem.refund_expect) ==
                                 refund_expect_year)
        if refund_situation == "還付予定":
            query = query.filter(LostItem.refund_situation == "還付予定")
        else:
            query = query.filter(LostItem.refund_situation == "還付済み")
        search_results = query.all()
        session['search_results'] = [item.to_dict() for item in search_results]
        return redirect(url_for("refund.print_list"))
    return render_template("refund/refund_list.html", all_lost_item=all_lost_item,
                           form=form)


# 一覧表の印刷
@refund.route("/print_list", methods=["POST", "GET"])
def print_list():
    search_results = session.get('search_results', [])
    form = RefundList()
    if form.submit.data:
        item_ids = request.form.getlist('item_ids')
        session['item_ids'] = item_ids
        items = db.session.query(LostItem).filter(LostItem.id.in_(item_ids)).all()
        make_pdf_refund_items(items)
        return redirect(url_for("refund.refund_list", items=items))
    return render_template("refund/print_list.html", form=form,
                           search_results=search_results)


def make_pdf_refund_items(items):
    file_name = "refund_item" + '.pdf'
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    p = canvas.Canvas(file_path, pagesize=landscape(A4))
    # ヘッダー部分(表までのテンプレ)
    p.setFont('HeiseiMin-W3', 20)
    p.drawString(350, 550, "還付請求一覧")
    p.setFont('HeiseiMin-W3', 10)
    p.drawString(750, 520, datetime.now().strftime("%Y年%m月%d日"))

    # 表の部分
    p.rect(20, 480, 80, 20), p.rect(100, 480, 80, 20), p.rect(180, 480, 80, 20)
    p.rect(260, 480, 80, 20), p.rect(340, 480, 80, 20), p.rect(420, 480, 320, 20)
    p.rect(740, 480, 80, 20)
    p.drawCentredString(60, 485, "還付予定日"), p.drawCentredString(140, 485, "受理番号")
    p.drawCentredString(220, 485, "警察届出日"), p.drawCentredString(300, 485, "拾得日時")
    p.drawCentredString(380, 485, "管理番号"), p.drawCentredString(580, 485, "物件の種類及び特徴")
    p.drawCentredString(780, 485, "金額")

    start_num = 450

    # 拾得物の内容記載
    for item in items:
        p.rect(20, start_num, 80, 30), p.rect(100, start_num, 80, 30)
        p.rect(180, start_num, 80, 30), p.rect(260, start_num, 80, 30)
        p.rect(340, start_num, 80, 30), p.rect(420, start_num, 320, 30)
        p.rect(740, start_num, 80, 30)

        denomination = Denomination.query.filter_by(lostitem_id=item.id).first()
        if item.refund_expect:
            p.drawCentredString(60, start_num+10,
                                item.refund_expect.strftime('%Y/%m/%d'))
        else:
            p.drawCentredString(60, start_num+10, "")
        p.drawCentredString(140, start_num+10, str(item.receiptnumber))
        if item.police_date:
            p.drawCentredString(220, start_num+10,
                                item.police_date.strftime('%Y/%m/%d'))
        else:
            p.drawCentredString(220, start_num+10, "")
        if item.get_item:
            p.drawCentredString(300, start_num+10, item.get_item.strftime('%Y/%m/%d'))
        else:
            p.drawCentredString(300, start_num+10, "")
        p.drawCentredString(380, start_num+10, str(item.main_id))
        p.drawCentredString(580, start_num+17, item.item_class_S)
        p.drawCentredString(580, start_num+5, item.item_feature)
        if denomination is not None:
            p.drawCentredString(780, start_num+10, str(denomination.total_yen))
        start_num -= 30

    # Close the PDF object cleanly.
    p.showPage()
    p.save()

    return "PDF receipt saved as " + file_name


# 還付済物件処理一覧
def make_refunded_list(items):
    file_name = "refunded" + '.pdf'
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    p = canvas.Canvas(file_path, pagesize=landscape(A4))
    # ヘッダー部分(表までのテンプレ)
    p.setFont('HeiseiMin-W3', 20)
    p.drawString(350, 550, "還付済物件処理一覧")
    p.setFont('HeiseiMin-W3', 10)
    p.drawString(750, 520, datetime.now().strftime("%Y年%m月%d日"))

    # 表の部分
    p.rect(20, 480, 80, 20), p.rect(100, 480, 80, 20), p.rect(180, 480, 80, 20)
    p.rect(260, 480, 80, 20), p.rect(340, 480, 80, 20), p.rect(420, 480, 320, 20)
    p.rect(740, 480, 80, 20)
    p.drawCentredString(60, 485, "還付日"), p.drawCentredString(140, 485, "管理・受理番号")
    p.drawCentredString(220, 485, "処理担当者"), p.drawCentredString(300, 485, "拾得日時")
    p.drawCentredString(380, 485, "金額"), p.drawCentredString(580, 485, "物件の種類及び特徴")
    p.drawCentredString(780, 485, "還付後処理")

    start_num = 450
    total_money = 0
    # 拾得物の内容記載
    for item in items:
        p.rect(20, start_num, 80, 30), p.rect(100, start_num, 80, 30)
        p.rect(180, start_num, 80, 30), p.rect(260, start_num, 80, 30)
        p.rect(340, start_num, 80, 30), p.rect(420, start_num, 320, 30)
        p.rect(740, start_num, 80, 30)

        denomination = Denomination.query.filter_by(lostitem_id=item.id).first()
        if item.refund_date:
            p.drawCentredString(60, start_num+10,
                                item.refund_date.strftime('%Y/%m/%d'))
        else:
            p.drawCentredString(60, start_num+10, "")
        p.drawCentredString(140, start_num+17, str(item.main_id))
        p.drawCentredString(140, start_num+5, str(item.receiptnumber))
        if item.refund_manager:
            p.drawCentredString(220, start_num+10, item.refund_manager)
        if item.get_item:
            p.drawCentredString(300, start_num+10, item.get_item.strftime('%Y/%m/%d'))
        else:
            p.drawCentredString(300, start_num+10, "")
        if denomination is not None:
            p.drawCentredString(380, start_num+10, str(denomination.total_yen))
        p.drawCentredString(580, start_num+17, item.item_class_S)
        p.drawCentredString(580, start_num+5, item.item_feature)
        if item.refunded_process:
            p.drawCentredString(780, start_num+10, item.refunded_process)
        else:
            p.drawCentredString(780, start_num+10, "")
        if denomination is not None:
            total_money += denomination.total_yen
        start_num -= 30

    # 合計金額の記載
    p.drawString(580, start_num, "合計金額")
    p.drawString(625, start_num, str(total_money) + "円")
    p.line(580, start_num-3, 680, start_num-3)

    # Close the PDF object cleanly.
    p.showPage()
    p.save()

    return "PDF receipt saved as " + file_name

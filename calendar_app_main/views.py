#Djangoで「どんなデータを作って」「どのテンプレートに渡すか」を決めるところ
from django.db import DatabaseError
from django.shortcuts import render, get_object_or_404,  redirect  # ページ表示やリダイレクトに使う
from datetime import date #Python にもともと入っている「日付や時間」を扱う datetime（デートタイム）モジュール の中から、その中の date クラス (日付（年月日）)だけを使えるようにする
import calendar #Pythonの標準ライブラリ「calendar（カレンダー）」モジュールを使う
import jpholiday  # 日本の祝日を判定できるライブラリ
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from .models import Event  # Eventモデルを読み込む
from .forms import EventForm   # イベント登録や編集に使うフォームを読み込み
from datetime import date, timedelta    # 日付操作に使う標準モジュール
from dateutil.relativedelta import relativedelta    # 「1か月後」などを簡単に計算できるモジュール
from datetime import date, timedelta, datetime

def calendar_view(request, year=None, month=None):
    """カレンダー表示メイン処理"""
    today = date.today()         # 今日の日付を取得

    try:
        # --- 年月指定がない場合は今日を使う ---
        if year is None or month is None:
            year = today.year
            month = today.month

        # --- URLパラメータを整数に変換（例: '2025' → 2025）---
        year = int(year)
        month = int(month)

        # --- 範囲チェック（前後10年以内）---
        min_year = today.year - 10
        max_year = today.year + 10
        if not (min_year <= year <= max_year):
            raise ValueError(f"指定できる範囲は {min_year}年〜{max_year}年 です。（指定：{year}年）")

        # --- 月の範囲チェック ---
        if not (1 <= month <= 12):
            raise ValueError("月は1〜12の範囲で指定してください。")

    except ValueError:
        # ===============================
        # 数字以外 or 範囲外など ValueError 系
        # ===============================
        error_message = f"""
        <h2>エラー</h2>
        <p>URLの指定が不正です。年と月は「半角数字のみ」で指定してください。</p>
        <p><a href="/{today.year}/{today.month}/">▶ 今月（{today.year}年{today.month}月）に戻る</a></p>
        """
        return HttpResponseBadRequest(error_message)

    except Exception as e:
        # ===============================
        # 想定外のエラー（デバッグ用）
        # ===============================
        error_message = f"""
        <h2>予期せぬエラーが発生しました</h2>
        <p>{e}</p>
        <p><a href="/{today.year}/{today.month}/">▶ 今月に戻る</a></p>
        """
        return HttpResponseBadRequest(error_message)

    # =====================================
    # ② カレンダー構造を作る（日曜始まり）
    # =====================================
    cal = calendar.Calendar(firstweekday=6)  
    month_days = cal.monthdayscalendar(year, month)
    week_days = ['日', '月', '火', '水', '木', '金', '土']

    # =====================================
    # ③ 表示範囲（その月の最初と最後の日）
    # =====================================
    start_of_month = date(year, month, 1)
    end_of_month = (start_of_month + relativedelta(months=1)) - timedelta(days=1)
    
    # =====================================
    # ④ 表示月に関係しているイベントを取得
    # （前月に始まって今月に食い込んでるものも含む）
    # =====================================
    events = Event.objects.filter(
        end_date__gte=start_of_month,
        start_date__lte=end_of_month
    ).order_by("start_date")    #開始が早い順に並べる。

    # =====================================
    # ⑤ 定数（セル幅・バー高さなど） CSS で描画するための座標計算に使う基準値
    # =====================================
    CELL_WIDTH_PX = 100 #1日分のセル（列）の横幅
    BORDER_PX = -4       #セルの境界線（罫線）の太さを加味するため
    BAR_HEIGHT_PX = 22  #縦方向の「ずらし量」(重なり回避用)

    # =====================================
    # ⑥ イベント描画用データを格納する辞書
    #   例： {14: [イベント1, イベント2], ...}
    # =====================================
    event_dict = {}

    # =====================================
    # ⑦ 月の各週を取得（7日単位）これで「その月の各週（7日分）」の日付を全部取得。
    # =====================================
    cal_weeks = cal.monthdatescalendar(year, month)  # 各週の日付リスト

    # =====================================
    # ⑧ 各週ごとにイベントを配置していく
    # =====================================
    for week in cal_weeks:
        # 週の開始・終了日
        week_start = week[0]
        week_end = week[-1]

        # --- この週にかかるイベントを抽出 ---
        week_events = [
            e for e in events
            if e.end_date >= week_start and e.start_date <= week_end
        ]

        # --- この週の中で使うレイヤー（縦位置）を記録するリスト ---
        week_layers = []  # 各レイヤーにイベントを配置

        # =====================================
        # ⑨ 各イベントを配置（重なり調整付き）
        # =====================================
        for e in week_events:
            # この週の中で見える開始日と終了日を計算
            vis_start = max(e.start_date, week_start, start_of_month)
            vis_end = min(e.end_date, week_end, end_of_month)

            # --- イベントの横幅を日数に応じて計算 ---
            span_days = (vis_end - vis_start).days + 1  # 期間の日数（例：3日間なら3）
            # 予定日数に応じてバーの補正量（BORDER_PX）を変える
            if span_days <= 3:
                border_px = -4   # 1～3日 
            elif span_days <= 3:
                border_px = -1.5   # 3日    
            elif span_days <= 5:
                border_px = -2   # 4～5日 
            else:
                border_px = -1    # 6～7日以上 
            span_px = span_days * CELL_WIDTH_PX + max(0, span_days - 1) * border_px

            # =====================================
            # ⑩ どの段（layer）に配置するか決定する処理
            # =====================================
            layer_index = 0
            while True:
                conflict = False    # 他イベントと重なってるかどうか
                # すでにその段にあるイベントと期間が重ならないか確認
                for existing in week_layers[layer_index] if layer_index < len(week_layers) else []:
                    if not (vis_end < existing["start"] or vis_start > existing["end"]):
                        conflict = True     # 重なってたら下の段に移動
                        break
                if not conflict:
                    break      # 重なってなければこの段に配置
                layer_index += 1

            # --- 必要に応じて新しい段（レイヤー）を追加 ---
            while len(week_layers) <= layer_index:
                week_layers.append([])

            # --- レイヤー情報を登録（この週の占有範囲を記録） ---
            week_layers[layer_index].append({"start": vis_start, "end": vis_end})

            # =====================================
            # ⑪ event_dict にテンプレート用データを登録
            # =====================================
            start_day_key = vis_start.day
            same_day_events = event_dict.setdefault(start_day_key, [])
            same_day_events.append({
                "id": e.id,
                "title": e.title,
                "color": e.color,
                "span": span_days,              # 何日続くか
                "span_px": span_px,             # バーの横幅（ピクセル）
                "order": layer_index,           # 縦位置（上から何段目）
                "z_index": 20 - layer_index,    # 重なり順（上にくる順）
                "is_start_day": True,           # この日から描画を開始するか
            })

    # =====================================
    # ⑫ 前月・翌月を計算（ページ切り替え用）
    # =====================================
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    # =====================================
    # ⑬ 曜日ごとの文字色設定（日曜赤・土曜青・祝日赤）
    # =====================================
    month_info = []
    for week in month_days:
        week_info = []
        for i, day in enumerate(week):
            if day == 0:
                week_info.append({'day': '', 'color': 'black'})
            else:
                this_date = date(year, month, day)
                if jpholiday.is_holiday(this_date):
                    color = 'red'
                elif i == 0:
                    color = 'red'
                elif i == 6:
                    color = 'blue'
                else:
                    color = 'black'
                week_info.append({'day': day, 'color': color})
        month_info.append(week_info)

    # --- 検索キーワードを取得 ---
    query = request.GET.get("q", "")
    search_results = None

    if query:
        # タイトルまたはメモなどで部分一致検索
        search_results = Event.objects.filter(title__icontains=query) | Event.objects.filter(detail__icontains=query)

    # =====================================
    # ⑭ テンプレートに渡すデータをまとめる
    # =====================================
    context = {
        'year': year,
        'month': month,
        'weeks': month_info,
        'week_days': week_days,
        'today': today.day if year == today.year and month == today.month else 0,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        "month_days": month_days,
        "event_dict": event_dict,
        "BAR_HEIGHT_PX": BAR_HEIGHT_PX,
        "query": query,                    # ← 検索ワード
        "search_results": search_results,  # ← 検索結果
        "current_month_url": f'/{today.year}/{today.month}/',
        'current_year': today.year,
        'current_month': today.month,
    }
    # =====================================
    # ⑮ HTML テンプレートを描画して返す
    # =====================================
    return render(request, 'calendar_app_main/calendar.html', context)

def add_event(request, year, month, day):
    """イベント追加ページ"""
    try:
        # 半角数字チェック（全角などが入っていた場合 ValueError）
        year = int(year)
        month = int(month)
        day = int(day)

        # 日付オブジェクトに変換（存在しない日付なら ValueError）
        selected_date = date(year, month, day)

    except ValueError:
        # 不正な入力（全角数字・存在しない日付など）
        today = date.today()
        error_message = f"""
        <h2>エラー</h2>
        <p>URLの指定が不正です。年・月・日は「半角数字のみ」で指定してください。</p>
        <p><a href="/{today.year}/{today.month}/">▶ 今月（{today.year}年{today.month}月）に戻る</a></p>
        """
        return HttpResponseBadRequest(error_message)

    # フォーム処理（通常通り）
    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('calendar_app_main:calendar_by_month', year=year, month=month)
    else:
        form = EventForm(initial={'start_date': selected_date, 'end_date': selected_date})

    return render(request, "calendar_app_main/add_event.html", {
        "form": form,
        "year": year,
        "month": month,
        "day": day
    })

def event_detail(request, event_id):
    """イベント詳細ページ"""
    # 指定されたIDの予定を取得。存在しなければ404エラーを出す
    event = get_object_or_404(Event, id=event_id)
    # event_detail.html テンプレートにデータを渡して表示
    return render(request, "calendar_app_main/event_detail.html", {"event": event})

def edit_event(request, event_id):
    """イベント編集ページ"""
    today = date.today()  # ← これが必要！

    try:
        # --- URLの event_id が数字でない場合 ---
        event_id = int(event_id)

        # --- IDに該当するイベントを取得 ---
        event = Event.objects.get(pk=event_id)

    except ValueError:
        # ===============================
        # event_id に数字以外が入っていた場合
        # ===============================
        error_message = f"""
        <h2>エラー</h2>
        <p>URLの指定が不正です。イベントIDは数字で指定してください。</p>
        <p><a href="/{today.year}/{today.month}/">▶ 今月（{today.year}年{today.month}月）に戻る</a></p>
        """
        return HttpResponseBadRequest(error_message)

    except Event.DoesNotExist:
        # ===============================
        # 指定されたイベントIDが存在しない場合
        # ===============================
        error_message = f"""
        <h2>エラー</h2>
        <p>指定されたイベント（ID: {event_id}）は存在しません。</p>
        <p><a href="/{today.year}/{today.month}/">▶ カレンダーに戻る</a></p>
        """
        return HttpResponseNotFound(error_message)

    except DatabaseError as e:
        # ===============================
        # DBエラー（通信・破損など）
        # ===============================
        error_message = f"""
        <h2>データベースエラー</h2>
        <p>{e}</p>
        <p><a href="/{today.year}/{today.month}/">▶ カレンダーに戻る</a></p>
        """
        return HttpResponseBadRequest(error_message)

    except Exception as e:
        # ===============================
        # 想定外のエラー（保険）
        # ===============================
        error_message = f"""
        <h2>予期せぬエラーが発生しました</h2>
        <p>{e}</p>
        <p><a href="/{today.year}/{today.month}/">▶ カレンダーに戻る</a></p>
        """
        return HttpResponseBadRequest(error_message)

    # ===============================
    # 正常処理（フォーム表示・更新）
    # ===============================
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            return redirect(
                'calendar_app_main:calendar_by_month',
                year=event.start_date.year,
                month=event.start_date.month
            )
    else:
        form = EventForm(instance=event)

    # 編集ページを表示
    return render(request, 'calendar_app_main/edit_event.html', {
        'form': form,
        'event': event,
        'year': event.start_date.year,
        'month': event.start_date.month,
    })

def delete_event(request, event_id):
    """イベント削除ページ"""   

    today = date.today()  # 今の日付を取得

    try:
        # --- URLの event_id が数字でない場合 ---
        event_id = int(event_id)

        # --- 指定されたIDのイベントを取得 ---
        event = Event.objects.get(pk=event_id)

    except ValueError:
        # ===============================
        # event_id が数字以外（例：全角、文字）だった場合
        # ===============================
        error_message = f"""
        <h2>エラー</h2>
        <p>URLの指定が不正です。イベントIDは半角数字で指定してください。</p>
        <p><a href="/{today.year}/{today.month}/">▶ カレンダーに戻る</a></p>
        """
        return HttpResponseBadRequest(error_message)

    except Event.DoesNotExist:
        # ===============================
        # 該当するイベントが存在しない場合
        # ===============================
        error_message = f"""
        <h2>エラー</h2>
        <p>指定されたイベント（ID: {event_id}）は存在しません。</p>
        <p><a href="/{today.year}/{today.month}/">▶ カレンダーに戻る</a></p>
        """
        return HttpResponseNotFound(error_message)

    except Exception as e:
        # ===============================
        # 想定外のエラー（保険）
        # ===============================
        error_message = f"""
        <h2>予期せぬエラーが発生しました</h2>
        <p>{e}</p>
        <p><a href="/{today.year}/{today.month}/">▶ カレンダーに戻る</a></p>
        """
        return HttpResponseBadRequest(error_message)

    if request.method == 'POST':
        # 削除前に日付を一時保存（削除後にページに戻るとエラーが起こるので）
        year = event.start_date.year
        month = event.start_date.month
        
        event.delete()  # 実際に削除

        # 削除後にカレンダーへ戻る（削除前に保存した日付を使用）
        return redirect('calendar_app_main:calendar_by_month', year=year, month=month)

    # GET の場合は確認画面を表示
    return render(request, 'calendar_app_main/delete_confirm.html', {'event': event})

def calendar_search(request):
    query = request.GET.get('q', '').strip()  # 検索キーワードを取得
    events = []

    if query:
        # タイトルまたはメモなど部分一致検索（必要に応じてフィールドを追加）
        events = Event.objects.filter(title__icontains=query)

    return render(request, 'calendar_app_main/calendar_search.html', {
        'query': query,
        'events': events,
    })

from django.utils import timezone  # ← これが重要！
from datetime import datetime, date, timedelta

def calendar_by_day(request, year, month, day):
    """日（時間）表示のカレンダー"""
    today = date.today()  # ← 今日の日を取得
    
    try:
        year = int(year)
        month = int(month)
        # 当月なら day を今日に、別の月なら 1 日に設定
        if year == today.year and month == today.month:
            day = today.day
        else:
            # URL に day が渡っていればそれを使い、なければ 1 日
            day = int(day) if day is not None else 1
        
        selected_date = date(year, month, day)
    except ValueError:
        # 不正な日付の場合は今月に戻るボタンを付けて返す
        html = f"""
        <h2>日付指定が不正です。</h2>
        <p>URLに存在しない日付、または正しくない形式が含まれています。</p>
        <p><a href='/{today.year}/{today.month}/'>カレンダーに戻る</a></p>
        """
        return HttpResponseBadRequest(html)
    
    # 時間リストを定義（0〜23時）
    hours = list(range(0, 24))

    # その日のイベント取得（開始日か終了日がその日を含む）
    events = Event.objects.filter(
        start_date__lte=selected_date,
        end_date__gte=selected_date
    ).order_by("start_date")

    # 前日・翌日を計算
    prev_date = selected_date - timedelta(days=1)
    next_date = selected_date + timedelta(days=1)

    # イベントごとの表示用データを計算
    for event in events:
        # 開始時刻（分単位）
        if hasattr(event, "start_time") and event.start_time:
            event.start_hour = event.start_time.hour * 60 + event.start_time.minute
        else:
            event.start_hour = 0

        # 終了時刻と差分（分単位）
        if hasattr(event, "end_time") and event.end_time and event.start_time:
            start_dt = timezone.make_aware(datetime.combine(date.today(), event.start_time))
            end_dt = timezone.make_aware(datetime.combine(date.today(), event.end_time))

            # もし終了が翌日（例: 23:30〜01:00）なら補正
            if end_dt < start_dt:
                end_dt += timedelta(days=1)

            delta = end_dt - start_dt
            event.duration_minutes = delta.total_seconds() // 60  # ← seconds属性の代わりにtotal_seconds()
        else:
            event.duration_minutes = 60  # デフォルト1時間

        # 背景色
        if not hasattr(event, "color") or not event.color:
            event.color = "#0078d7"

    columns = []  # 同時刻に重なるイベントのグループ

    for event in events:
        placed = False
        for col in columns:
            last_event = col[-1]
            if (
                last_event.end_time
                and event.start_time
                and event.start_time >= last_event.end_time
            ):
                col.append(event)
                placed = True
                break
        if not placed:
            columns.append([event])
                
    # 各イベントに「列番号」と「全列数」をセット
    for col_index, col in enumerate(columns):
        for e in col:
            e.column_index = col_index
            e.total_columns = len(columns)


    # ✅ テンプレートへ渡す
    context = {
        "year": year,
        "month": month,
        "day": day,
        "hours": hours,
        "events": events,
        "prev_year": prev_date.year,
        "prev_month": prev_date.month,
        "prev_day": prev_date.day,
        "next_year": next_date.year,
        "next_month": next_date.month,
        "next_day": next_date.day,
        'current_day': today.day, 
    }

    return render(request, "calendar_app_main/calendar_by_day.html", context)

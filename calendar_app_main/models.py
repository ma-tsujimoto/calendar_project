from django.db import models  # Djangoのデータベース機能を使うために読み込む

class Event(models.Model):  
    title = models.CharField(max_length=10)           # 予定のタイトル(文字数指定)
    detail = models.TextField(blank=True, null=True)  # 詳細（空でもOK）
    start_date = models.DateField()                   # 開始日
    end_date = models.DateField()                     # 終了日
    start_time = models.TimeField(null=True, blank=True)  # 開始時間
    end_time = models.TimeField(null=True, blank=True)    # 終了時間
    color = models.CharField(max_length=20, default="#b3d7ff")  # バーの色

    def __str__(self):
        # 開始日とタイトルを一緒に見やすく表示
        return f"{self.start_date} - {self.title}"

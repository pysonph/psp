# 1. ပေါ့ပါးသော Python 3.11-slim ကို အခြေခံအဖြစ် အသုံးပြုမည်
FROM python:3.11-slim

# 2. Python နှင့် System အတွက် လိုအပ်သော အရေးကြီး Environment များကို သတ်မှတ်မည်
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Yangon

# 3. အလုပ်လုပ်မည့် နေရာကို /app ဟု သတ်မှတ်မည်
WORKDIR /app

# 4. အချိန်မှန်ကန်စေရန် tzdata ကို အရင်သွင်းမည်
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends tzdata && \
    rm -rf /var/lib/apt/lists/*

# 5. Requirements ကို အရင် Copy ကူးမည် (Docker Layer Cache ကို အသုံးချရန်)
COPY requirements.txt .

# 6. Python Packages များကို သွင်းမည်၊ ထို့နောက် Playwright အတွက် Chromium နှင့် System Deps များကို သွင်းမည်
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium --with-deps && \
    # Image Size သေးငယ်စေရန် မလိုအပ်သော Cache များကို ရှင်းလင်းမည်
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cache/*

# 7. ကျန်ရှိသော Bot ၏ Code ဖိုင်များအားလုံးကို Container ထဲသို့ ကူးထည့်မည်
COPY . .

# 8. Bot ကို စတင် Run မည် (ဖိုင်နာမည်ကို wanglin.py ဟု ပြင်ဆင်ထားသည်)
CMD ["python3", "psp.py"]

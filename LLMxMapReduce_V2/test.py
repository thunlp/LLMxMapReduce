import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://yeysai.com/v1/"
)


os.environ["PROMPT_LANGUAGE"]="zh"
from src.prompts import POLISH_PROMPT

content = "## 2.3 不同收入群体的负担\n关税政策 оказывают непропорционально сильное воздействие на домохозяйства с низкими доходами。多项研究和分析均指出，低收入家庭在关税和物价上涨的压力下首当其冲 [1,5,7,15,22,27]。这主要是因为低收入家庭的收入结构和消费模式具有特殊性。他们的收入中更大比例用于食品、服装、日用品等生活必需品消费，对物价变动更为敏感 [1,5,22,38]。因此，当关税导致物价普遍上涨，特别是食品等必需品价格上涨时，低收入家庭的可支配收入将受到更大程度的侵蚀，生活成本压力显著增加 ([15], [16], [26], [8], [7], [32], [11], [12], [27], [3], [9], [10], [34], [22])。\n\n量化分析显示，不同收入阶层家庭因关税增加的支出负担存在显著差异。\n"

prompt = POLISH_PROMPT.format(content = content)

response = client.chat.completions.create(
    model="claude-3-5-haiku-20241022",
    messages=[
        {"role": "user", "content": prompt}
    ]
)

print(response)

import csv
import os
import json
from openai import OpenAI

# Use the built-in OpenAI client (base_url and api_key are pre-configured in environment)
client = OpenAI()

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def generate_drafts():
    # Load inputs
    customers_path = '/home/ubuntu/upload/customers.csv'
    skill_path = '/home/ubuntu/upload/GRADO商务邮件写作规范（EmailWritingSkill）.md'
    prompt_path = '/home/ubuntu/AI_sales_email_agent/prompts/email_generation_prompt.md'
    
    writing_skill = read_file(skill_path)
    base_prompt = read_file(prompt_path)
    
    output_path = '/home/ubuntu/AI_sales_email_agent/data/drafts/drafts.csv'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(customers_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        customers = list(reader)
    
    results = []
    
    for customer in customers:
        print(f"Generating draft for {customer['name']} at {customer['company']}...")
        
        user_input = f"""
客户信息：
姓名：{customer['name']}
公司：{customer['company']}
职位：{customer['position']}
行业：{customer['industry']}
地区：{customer['location']}
公司类型：{customer['company_type']}
"""
        
        system_prompt = f"""你是一个专业的商务邮件写作助手，代表 GRADO CONTRACT 品牌。
请严格遵循以下品牌写作规范：
{writing_skill}

生成指令如下：
{base_prompt}

请根据客户信息生成邮件。注意语言选择规则：如果是中文背景客户用中文，如果是国际/英文背景客户用英文。
"""

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "email_draft",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string"},
                            "body": {"type": "string"},
                            "personalization_note": {"type": "string"},
                        },
                        "required": ["subject", "body", "personalization_note"],
                        "additionalProperties": False,
                    },
                },
            },
        )
        
        draft = json.loads(response.choices[0].message.content)
        draft['customer_id'] = customer['id']
        draft['email'] = customer['email']
        draft['review_status'] = 'pending'
        results.append(draft)
    
    # Write results to CSV
    fieldnames = ['customer_id', 'email', 'subject', 'body', 'personalization_note', 'review_status']
    with open(output_path, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)
            
    print(f"✅ Successfully generated {len(results)} drafts to {output_path}")

if __name__ == "__main__":
    generate_drafts()

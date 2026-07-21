#本工具解决了原md文档只有一级#标题的问题，现在他可以产生#####的五级标题了#
import re

def fix_markdown_hierarchy(input_filepath, output_filepath):
    with open(input_filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    fixed_lines = []
    
    # 🌟 状态机：记录当前阅读所在的上下文区域
    in_exercises = False
    is_answer_section = False
    
    for line in lines:
        stripped_line = line.strip()
        
        if not stripped_line:
            fixed_lines.append(line)
            continue
            
        # 1. 匹配书末独立章节：“习题答案与提示”
        if re.match(r'^#\s*(习题答案|提示与答案|答案)', stripped_line):
            is_answer_section = True
            in_exercises = False
            fixed_lines.append('# ' + stripped_line.lstrip('# ') + '\n')
            continue
            
        # 2. 匹配“章”与“引言” 
        if re.match(r'^#\s*(第[\d一二三四五六七八九十百]+章|引言)', stripped_line):
            in_exercises = False 
            fixed_lines.append(line)
            continue
            
        # 3. 匹配“节” 
        if re.match(r'^#\s*\d+\.\d+\s+', stripped_line):
            in_exercises = False
            fixed_lines.append(line.replace('#', '##', 1))
            continue
            
        # 4. 匹配“小节” 
        if re.match(r'^#\s*\d+\.\d+\.\d+\s+', stripped_line):
            in_exercises = False
            fixed_lines.append(line.replace('#', '###', 1))
            continue
            
        # 5. 匹配“习题”
        if re.match(r'^#\s*习题', stripped_line):
            in_exercises = True
            fixed_lines.append(line.replace('#', '###', 1))
            continue
            
        # 6. 保留“一、二、”等宏观概念分组为四级标题
        if re.match(r'^#\s*[一二三四五六七八九十]+、', stripped_line):
            fixed_lines.append(line.replace('#', '####', 1))
            continue
            
        # 7. 🔥 正文核心实体捕获 (定理、定义、例题等)
        match_A = re.match(r'^[\*\s\d\.]*((?:定理|定义|引理|推论|性质|例|命题)\s*[\d\.]*)([\*\s\(\)（）:：]+|$)', stripped_line)
        match_B = re.match(r'^[\*\s]*\d+[\.\s]+.{0,25}?((?:定理|定义|引理|推论|性质|例|命题))[：:]\s*\**\s*$', stripped_line)
        
        if match_A or match_B:
            clean_line = re.sub(r'^\*+(.*?)\*+', r'\1', stripped_line).lstrip('* ')
            if match_A:
                entity_name = match_A.group(1).replace(' ', '')
            else:
                entity_name = clean_line.rstrip('：*: ') 
            
            fixed_lines.append(f'##### {entity_name}\n')
            fixed_lines.append(clean_line + '\n')
            continue
            
        # 8. 🚀 题目与答案捕获 
        if in_exercises:
            match_ex = re.match(r'^[\*\s]*(\d+)\.(?!\d)', stripped_line)
            if match_ex:
                item_num = match_ex.group(1) 
                prefix = "答案" if is_answer_section else "题"
                entity_name = f"{prefix}{item_num}"
                clean_line = re.sub(r'^\*+(.*?)\*+', r'\1', stripped_line).lstrip('* ')
                
                fixed_lines.append(f'##### {entity_name}\n')
                fixed_lines.append(clean_line + '\n')
                continue
                
        # 9. 过滤零散不规范的井号干扰
        if stripped_line.startswith('#'):
            clean_hash = stripped_line.lstrip('# ')
            fixed_lines.append(f'**{clean_hash}**\n') 
            continue
            
        # 10. 其他所有普通段落原样保留
        fixed_lines.append(line)

    with open(output_filepath, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)
    
    print(f"处理完成！高质量结构化图谱源文件已生成: {output_filepath}")

# ====== 执行命令区 ======
# 指定你的输入文件（你刚刚上传的那个）和输出文件
input_file = "高等代数创新教材_下_丘维声.不删减.md"
output_file = "structured_高代下.md"

# 开始执行清洗
fix_markdown_hierarchy(input_file, output_file)
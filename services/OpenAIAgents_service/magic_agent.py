# services/OpenAIAgents_service/magic_agent.py

from services.config_service import config_service
from typing import Dict, Any, List
from agents import Agent, Runner, set_tracing_disabled, set_default_openai_key, ImageGenerationTool,TResponseInputItem
import asyncio
import re
import os
from nanoid import generate
from tools.utils.image_canvas_utils import save_image_to_canvas
from tools.utils.image_utils import get_image_info_and_save
from services.config_service import FILES_DIR

async def create_magic_response(messages: List[Dict[str, Any]], session_id: str = "", canvas_id: str = "") -> Dict[str, Any]:
    try:
        # 获取图片内容
        user_message: Dict[str, Any] = messages[-1]
        image_content: str = ""
        
        if isinstance(user_message.get('content'), list):
            for content_item in user_message['content']:
                if content_item.get('type') == 'image_url':
                    image_content = content_item.get('image_url', {}).get('url', "")
                    break
        
        if image_content:
            # set agents
            set_tracing_disabled(True)
            config = config_service.get_config()
            api_key = config.get('openai', {}).get('api_key', '')
            set_default_openai_key(str(api_key))

            intent_agent = Agent(
                name="Intent Agent",
                instructions='''你是一个强大艺术洞察助手，你指导下游的图像生成助手根据用户的需求生成图像。
你有强大的用户意图理解能力，能根据用户的草图理解用户想要什么。
最终输出的图像不仅内容要符合用户意图，还要保证图像艺术风格与意图相匹配。
必须给出目标图像的尺寸比率建议（目标图像有可能不是输入的草图的初始的大小，而是草图上某个区域作业区域的尺寸）。''',
                model="gpt-4.1-mini",
            )

            draw_agent = Agent(
                name="Draw Agent",
                instructions='''你是一个顶尖的图像生成助手。
根据用户提供的草图分析，生成符合以下要求的图像：
1) 风格现代、美观 2) 符合用户创作意图 3) 避免任何可能违反内容政策的内容 4) 如果用户有明确的要求，则想办法在满足用户要求的同时避免违反内容政策。
请使用imageGenerationTool生成图像，必须遵从上下文给出的尺寸比率建议，如果上下文没有给出尺寸建议，则生成图像的尺寸是512*512或对应的质量。
如果有角色，尽可能保持角色长相气质与原来一致。''',
                model="gpt-4.1-mini",
                tools=[ImageGenerationTool(
                    tool_config={
                        "type": "image_generation",
                        "model": "gpt-image-1",
                    }
                )],
                tool_use_behavior="stop_on_first_tool",
            )
            
            # Run
            thread: List[TResponseInputItem] = []
            thread.append({  # type: ignore
                'role': 'user', 
                'content': [
                    {
                        'type': 'input_image',
                        'image_url': image_content
                    },
                    {
                        'type': 'input_text',
                        'text': 'Please analyze this image and generate a new one based on it.'
                    }
                ],
            })

            result_intent = await Runner.run(intent_agent, thread)
            print(result_intent.final_output)
            thread = result_intent.to_input_list()
            
            result_draw = await Runner.run(draw_agent, thread)
            print("result_draw 对象属性:")
            print(f"final_output: {result_draw.final_output}")

            # 获取图片URL
            image_url = ""
            for item in result_draw.new_items:
                if item.type == 'tool_call_item' and item.raw_item.type == 'image_generation_call':
                    image_url = item.raw_item.result
                    if image_url and session_id and canvas_id:
                        try:
                            # 生成唯一文件名
                            file_id = generate(size=10)
                            file_path_without_extension = os.path.join(FILES_DIR, file_id)
                            
                            # 处理base64图片数据并保存到文件
                            mime_type, width, height, extension = await get_image_info_and_save(
                                image_url, file_path_without_extension, is_b64=True
                            )

                            width = max(1, int(width / 2))
                            height = max(1, int(height / 2))
                            
                            # 生成完整文件名
                            filename = f"{file_id}.{extension}"
                            
                            # 保存图片到画布
                            await save_image_to_canvas(session_id, canvas_id, filename, mime_type, width, height)
                            print(f"✨ 图片已保存到画布: {filename}")
                        except Exception as e:
                            print(f"❌ 保存图片到画布失败: {e}")
                        break

            return {
                'role': 'assistant',
                'content': [
                    {
                        'type': 'text',
                        'text': '✨ Magic Success!!!'
                    },
                ]
            }
        else:
            return {
                'role': 'assistant',
                'content': [
                    {
                        'type': 'text',
                        'text': '✨ not found input image'
                    }
                ]
            }
            
    except (asyncio.TimeoutError, Exception) as e:
        # 检查是否是超时相关的错误
        error_msg = str(e).lower()
        if 'timeout' in error_msg or 'timed out' in error_msg:
            return {
                'role': 'assistant',
                'content': [
                    {
                        'type': 'text',
                        'text': '✨ time out'
                    }
                ]
            }
        else:
            print(f"创建魔法回复时出错: {e}")
            return {
                'role': 'assistant',
                'content': [
                    {
                        'type': 'text',
                        'text': f'✨ Magic Generation Error: {str(e)}'
                    }
                ]
            }

def extract_image_url_from_result(result_text: str) -> str:
    """从结果文本中提取图片URL"""
    # 尝试匹配图片URL模式
    url_pattern = r'https?://[^\s]+\.(png|jpg|jpeg|webp)'
    match = re.search(url_pattern, result_text)
    if match:
        return match.group(0)
    
    # 如果没有找到URL，返回空字符串
    return ""

if __name__ == "__main__":
    asyncio.run(create_magic_response([]))
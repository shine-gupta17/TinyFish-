import requests
from io import BytesIO
from groq import Groq
from openai import OpenAI
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain.output_parsers import BooleanOutputParser
from langchain_core.runnables import RunnableSequence
from pydantic import BaseModel, Field
import json
import os


class AIDecisionResponse(BaseModel):
    """Pydantic model for AI decision responses"""
    decision: bool = Field(description="Whether the message satisfies the condition (true/false)")


class AIResponser:
    def __init__(self):
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Type-based configuration
        self.request_type_configs = {
            "comment_reply": {
                "temperature": 0.3,
                "max_tokens": 50,
                "system_prompt": "Respond briefly and clearly to the comment."
            },
            "long_reply": {
                "temperature": 0.7,
                "max_tokens": 200,
                "system_prompt": "Write a detailed and thoughtful reply."
            },
            "casual_reply": {
                "temperature": 0.6,
                "max_tokens": 100,
                "system_prompt": "Reply in a casual and friendly tone."
            },
            "default": {
                "temperature": 0.5,
                "max_tokens": 150,
                "system_prompt": ""
            }
        }

    def query(
        self,
        template: str,
        model_provider: str = "OPENAI",
        model_name: str = "gpt-4o-mini",
        request_type: str = "default",
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None
    ):
        """
        Query using OpenAI GPT-4o-mini (forced default).
        Returns dict with content and tokens.
        """
        print("=== AIResponser.query DEBUG ===")
        print(f"Template: {template}")
        
        # Force OpenAI GPT-4o-mini regardless of parameters
        model_provider = "OPENAI"
        model_name = "gpt-4o-mini"
        
        print(f"Forced Model Provider: {model_provider}")
        print(f"Forced Model Name: {model_name}")
        print(f"Request Type: {request_type}")
        print(f"System Prompt: {system_prompt}")
        
        if not template or template.strip() == "":
            print("ERROR: Empty template provided")
            return None

        # Get config for request_type
        config = self.request_type_configs.get(request_type, self.request_type_configs["default"])
        print(f"Config: {config}")

        # Use overrides if provided, else fallback to config
        final_temperature = temperature if temperature is not None else config["temperature"]
        final_max_tokens = max_tokens if max_tokens is not None else config["max_tokens"]
        final_system_prompt = system_prompt if system_prompt is not None else config.get("system_prompt", "")
        
        print(f"Final params - Temp: {final_temperature}, Max tokens: {final_max_tokens}")

        # Build messages
        messages = []
        if final_system_prompt:
            messages.append({"role": "system", "content": final_system_prompt})
        messages.append({"role": "user", "content": template})
        
        print(f"Messages: {messages}")

        # Always use OpenAI
        result = self._openai_response(model_name, messages, final_temperature, final_max_tokens)
            
        print(f"Final result: {result}")
        print("=== END DEBUG ===")
        return result

    def _groq_response(self, model_name: str, messages: list, temperature: float, max_tokens: int):
        try:
            response = self.groq_client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                top_p=0.95,
                max_tokens=max_tokens,
                stream=False
            )
            print("response of groq ai : ",response)
            # Return both content and token usage
            content = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
            return {
                "content": content,
                "tokens": tokens_used
            }
        except Exception as e:
            print(f"GROQ error: {e}")
            return {
                "content": "GROQ error.",
                "tokens": 0
            }

    def _openai_response(self, model_name: str, messages: list, temperature: float, max_tokens: int):
        try:
            response = self.openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            # Return both content and token usage
            content = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
            return {
                "content": content,
                "tokens": tokens_used
            }
        except Exception as e:
            print(f"OpenAI error: {e}")
            return {
                "content": "OpenAI error.",
                "tokens": 0
            }

    def rule_based_ai(self, ai_rule: str, query: str, model_provider: str = "groq", model_name: str = "meta-llama/llama-4-maverick-17b-128e-instruct"):
        """
        Rule-based AI decision using OpenAI GPT-4o-mini with Pydantic structured output.
        Returns: {"is_match": bool, "tokens": int}
        """
        print("rule based ai ======> ")
        try:
            # Force OpenAI GPT-4o-mini for all AI decisions
            model_provider = "openai"
            model_name = "gpt-4o-mini"
            
            print(f"Using forced model: {model_provider} - {model_name}")
            
            # Use OpenAI's structured output with Pydantic
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert at evaluating messages against conditions. Analyze if the message satisfies the given condition and respond with a structured decision."
                },
                {
                    "role": "user",
                    "content": f"Condition: {ai_rule}\n\nMessage: {query}\n\nDoes this message satisfy the condition? Provide your decision."
                }
            ]
            
            # Use structured output with response_format
            response = self.openai_client.beta.chat.completions.parse(
                model=model_name,
                messages=messages,
                temperature=0.1,
                max_tokens=20,
                response_format=AIDecisionResponse
            )
            
            tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
            
            # Parse the structured response
            parsed_response = response.choices[0].message.parsed
            is_match = parsed_response.decision if parsed_response else False
            
            print("condition:", ai_rule)
            print("message:", query)
            print("is matched:", is_match)
            print(f"tokens used: {tokens_used}")
            
            return {"is_match": is_match, "tokens": tokens_used}

        except Exception as e:
            print(f"Error in rule_based_ai: {e}")
            # Fallback to simple JSON mode if structured output fails
            try:
                print("Falling back to JSON mode...")
                messages = [
                    {
                        "role": "system",
                        "content": "You are an expert at evaluating messages. Respond only with JSON format: {\"decision\": true/false}"
                    },
                    {
                        "role": "user",
                        "content": f"Condition: {ai_rule}\n\nMessage: {query}\n\nDoes this message satisfy the condition?"
                    }
                ]
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.1,
                    max_tokens=20,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content.strip()
                tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
                
                # Parse JSON response
                result = json.loads(content)
                is_match = result.get("decision", False)
                
                print("Fallback result - is matched:", is_match)
                print(f"tokens used: {tokens_used}")
                
                return {"is_match": is_match, "tokens": tokens_used}
                
            except Exception as fallback_error:
                print(f"Fallback also failed: {fallback_error}")
                return {"is_match": False, "tokens": 0}

import fitz  # this is pymupdf
def extract_text_from_pdf(pdf_url: str) -> str:
    """Download PDF and extract text from it."""
    response = requests.get(pdf_url)
    response.raise_for_status()

    pdf_stream = BytesIO(response.content)
    doc = fitz.open(stream=pdf_stream, filetype="pdf")

    text = ""
    for page in doc:
        text += page.get_text()

    doc.close()
    return text

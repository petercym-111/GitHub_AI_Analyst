get_weather_tool = {

    # Specifically for LLM to read, to use it for inference
    # Machine-readable contract advertised to the LLM.  It declares what the
    # model may request but does not execute anything; execution is separately
    # restricted by `TOOL_REGISTRY`, so both modules must stay synchronized.

        "type": "function",

        "name": "get_weather", # 这个必须100%跟 tool_registry 里的名字（registry key）一模一样，不然就会 KeyError。就算这里写weather ，但registry 里写 get_weather。 依然是不match的。

        "description": # 这里告诉LLM 让它知道, 什么时候调用。类似于tool 的 prompt， 关键字眼例如：name：get_weather ； description 里也强烈建议得有一个weather 的字眼。 描述包括得越精准，LLM 更容易正确匹配。
        "Retrieves current weather for a location.",

        # JSON Schema
        # 告诉 LLM： 调用 Tool 必须提供哪些parameters。 LLM 会根据用户回答自动填上这些 parameters。 如果没有parameters ，LLM 不知道需要哪些参数。
        "parameters": {

            "type": "object",

            "properties": { # 这里只是在定义：每一个参数。例如parameters 里有 location 和 units 这两个参数

                "location": {
                    "type": "string",

                   # 这个是 location 的 description。 每个 parameter 也可以有 description， 用来帮助 LLM 更加理解这个 parameter 到底长什么样。
                    "description": # description 和 enum 的区别： 告诉 LLM「这个参数是什么」。
                    "City and country"
                },

                "units": {

                    "type": "string",

                    # An enum prevents ambiguous output such as "C" or a
                    # value unsupported by `WeatherClient`.
                    "enum": [ # 用来严格限制 LLM 只能输出这两个，不能有别的。 限制 LLM「这个参数只能有哪些值」。
                        "celsius",
                        "fahrenheit"
                    ]

                }

            },

            "required": [ # 告诉 LLM ，所提到的这两个 parameters 是必须要提供的。确保这两个参数不会缺少
                "location",
                "units"
            ],

            # Reject undeclared keys rather than silently ignoring them; this
            # keeps the model-to-tool interface explicit as it evolves.
            # {
            #     "location":"KL",
            #
            #     "units":"celsius",
            #
            #     "country":"Malaysia"
            # }
            # like the example above LLM emitted, there is no "country" in the schema declared, so result in Validation Error to prevent the model from getting anything unvalidated
            "additionalProperties": False
        },

        # Ask the "provider" to enforce this JSON Schema instead of treating it
        # merely as guidance before the executor receives the arguments.
        # The "provider" is the company that owned the LLM (Groq in this project), so that the provider's API will validate the JSON schema for you
        "strict": True
    }


from fastapi import FastAPI
import uvicorn

from pkg.config.config import Settings

# Initialize settings (reads from .env automatically)
# settings = Settings()
# print(settings)




s = ("pen is on the table dklfnvje fkjr kv  iwnbrif oibrejhfbioheiu iohrjg oiwh4ruof oiw4hfiou oi4hfoiu . \nBook is beside the pen. There is pager alongside with book."
     "ndkjfrbvjk jrnij k wberiufbk werfujwerfb \n\n jbsrifwbfiuwneofbiywefun wkjevfuybqeojf jgevfiun vakbuyer urbfunwojrfb8eof weuifbuwi4befkj wfywbefh 2")
print(s.split("\n\n"))

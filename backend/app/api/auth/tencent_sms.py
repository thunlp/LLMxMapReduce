from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.sms.v20210111 import sms_client, models
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile


class TencentSMS:
    """腾讯云短信发送工具类"""

    def __init__(self, secret_id, secret_key, sdk_app_id, sign_name, region="ap-guangzhou"):
        """
        初始化腾讯云短信发送工具

        Args:
            secret_id: 腾讯云API密钥ID
            secret_key: 腾讯云API密钥Key
            sdk_app_id: 短信应用ID
            sign_name: 短信签名
            region: 地域，默认为广州
        """
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.sdk_app_id = sdk_app_id
        self.sign_name = sign_name
        self.region = region

    def send_verification_code(self, phone_number, code, template_id, minutes=10):
        """
        发送验证码短信

        Args:
            phone_number: 手机号码，格式为: 8613800138000 或 13800138000
            code: 验证码
            template_id: 模板ID
            minutes: 验证码有效期（分钟）

        Returns:
            dict: 发送结果
        """
        try:
            # 确保手机号格式正确（添加国家码前缀）
            if not phone_number.startswith('+'):
                # 如果没有+号前缀，检查是否有国家码
                if phone_number.startswith('86') or phone_number.startswith('0086'):
                    # 提取手机号部分（去掉国家码）
                    pure_number = phone_number[2:] if phone_number.startswith('86') else phone_number[4:]
                    phone_number = f"+86{pure_number}"
                else:
                    # 默认添加中国国家码
                    phone_number = f"+86{phone_number}"

            # 实例化一个认证对象
            cred = credential.Credential(self.secret_id, self.secret_key)

            # 实例化一个http选项，可选的，没有特殊需求可以跳过
            httpProfile = HttpProfile()
            httpProfile.reqMethod = "POST"  # post请求(默认为post请求)
            httpProfile.reqTimeout = 30  # 请求超时时间，单位为秒(默认60秒)
            httpProfile.endpoint = "sms.tencentcloudapi.com"  # 指定接入地域域名(默认就近接入)

            # 实例化一个客户端配置对象
            clientProfile = ClientProfile()
            clientProfile.signMethod = "TC3-HMAC-SHA256"  # 指定签名算法
            clientProfile.language = "zh-CN"
            clientProfile.httpProfile = httpProfile

            # 实例化要请求产品(以sms为例)的client对象
            client = sms_client.SmsClient(cred, self.region, clientProfile)

            # 实例化一个请求对象
            req = models.SendSmsRequest()

            # 设置短信应用ID
            req.SmsSdkAppId = self.sdk_app_id

            # 设置短信签名
            req.SignName = self.sign_name

            # 设置模板ID
            req.TemplateId = template_id

            # 模板参数: 验证码和有效期（分钟）
            req.TemplateParamSet = [str(code), str(minutes)]

            # 下发手机号码，采用 E.164 标准，格式为+[国家或地区码][手机号]
            req.PhoneNumberSet = [phone_number]

            # 用户的 session 内容，可以携带用户侧 ID 等上下文信息
            req.SessionContext = ""

            # 短信码号扩展号，默认未开通
            req.ExtendCode = ""

            # 国内短信无需填写该项；国际/港澳台短信已申请独立SenderId需要填写该字段
            req.SenderId = ""

            # 发送短信
            resp = client.SendSms(req)

            # 输出json格式的字符串回包
            return {
                "success": True,
                "message": "短信发送成功",
                "response": resp.to_json_string()
            }

        except TencentCloudSDKException as err:
            return {
                "success": False,
                "message": f"短信发送失败: {err}",
                "error": str(err)
            }
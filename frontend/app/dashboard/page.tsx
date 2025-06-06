"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Search, Send, Upload, Globe, ThumbsUp, MessageSquare, Clock, ChevronDown, RefreshCw } from "lucide-react"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"
import { useAuth } from "@/contexts/auth-context"
import { submitTask, getUserTasks } from "@/lib/api"
import { toast } from "sonner"

// 添加任务接口类型定义
interface UserTask {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  params: {
    topic: string;
    user_id: number;
  };
  execution_seconds?: number;
  start_time?: string;
  end_time?: string;
}

export default function DashboardPage() {
  const [topic, setTopic] = useState("")
  const [keywords, setKeywords] = useState("")
  const [language, setLanguage] = useState("zh")
  const [isGenerating, setIsGenerating] = useState(false)
  const [tasks, setTasks] = useState<UserTask[]>([])
  const [isLoadingTasks, setIsLoadingTasks] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const { token, user, isLoading, refreshUserInfo } = useAuth()
  const router = useRouter()

  // 检查登录状态
  useEffect(() => {
    if (!isLoading && !token) {
      toast.error("请先登录")
      router.push("/login")
    }
  }, [token, isLoading, router])

  // 获取用户任务列表
  const fetchUserTasks = async () => {
    if (!token) return
    
    setIsLoadingTasks(true)
    try {
      const response = await getUserTasks(token)
      if (response.success) {
        // 根据实际API响应格式，tasks直接在response中
        setTasks(response.tasks || [])
      } else {
        toast.error("获取任务列表失败", {
          description: response.message || "未知错误",
        })
      }
    } catch (error: any) {
      toast.error("获取任务列表失败", {
        description: error.message || "网络错误或服务器异常",
      })
    } finally {
      setIsLoadingTasks(false)
    }
  }

  // 在组件加载时获取任务列表
  useEffect(() => {
    if (token) {
      fetchUserTasks()
    }
  }, [token])

  // 如果正在加载或未登录，显示加载状态
  if (isLoading || !token) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-lg">加载中...</p>
          </div>
        </main>
        <Footer />
      </div>
    )
  }

  const handleGenerate = async () => {
    if (!token) {
      toast.error("请先登录", {
        description: "您需要登录后才能提交任务",
      })
      return
    }

    if (!topic) {
      toast.error("请输入文章标题", {
        description: "文章标题不能为空",
      })
      return
    }

    setIsGenerating(true)
    
    try {
      const response = await submitTask(token, topic, keywords || undefined)
      // 根据后端返回的success字段判断是否成功
      if (response.success) {
        toast.success("提交成功", {
          description: response.message || `任务ID: ${response.data.task_id}\n标题: ${response.data.unique_survey_title}`,
        })
        
        // 刷新用户信息以更新剩余次数
        await refreshUserInfo()
        
        // 重新获取任务列表
        await fetchUserTasks()
        
        // 清空输入框
        setTopic("")
        setKeywords("")
      } else {
        toast.error("提交失败", {
          description: response.message || "任务提交失败",
        })
      }
      
    } catch (error: any) {
      toast.error("提交失败", {
        description: error.message || "网络错误或服务器异常",
      })
    } finally {
      setIsGenerating(false)
    }
  }

  // 过滤任务列表
  const filteredTasks = tasks.filter(task =>
    task.params.topic.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // 获取状态显示文本
  const getStatusText = (status: string) => {
    switch (status) {
      case 'pending':
        return '待处理'
      case 'preparing':
        return '准备中'
      case 'searching':
        return '生成查询中'
      case 'searching_web':
        return '搜索网页中'
      case 'crawling':
        return '爬取内容中'
      case 'processing':
        return '处理中'
      case 'completed':
        return '已完成'
      case 'failed':
        return '失败'
      case 'timeout':
        return '超时'
      default:
        return status
    }
  }

  // 获取状态颜色
  const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
    switch (status) {
      case 'completed':
        return 'default'
      case 'preparing':
      case 'searching':
      case 'searching_web':
      case 'crawling':
      case 'processing':
        return 'secondary'
      case 'failed':
      case 'timeout':
        return 'destructive'
      case 'pending':
      default:
        return 'outline'
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 py-8">
        <div className="container max-w-5xl mx-auto px-4">
          {/* Main Input Card */}
          <Card className="border border-gray-200 dark:border-gray-800 shadow-sm mb-8">
            <CardContent className="p-6">
              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-medium">文章标题：</h3>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm text-muted-foreground">剩余次数：</span>
                      <Badge variant="outline">{user?.remaining_uses || 0}</Badge>
                    </div>
                  </div>
                  <Input
                    id="topic"
                    placeholder="请输入论文主题，10-100个字符"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    className="text-base py-6"
                  />
                </div>

                <div className="space-y-2">
                  <h3 className="text-lg font-medium">检索关键词：</h3>
                  <Input
                    id="keywords"
                    placeholder="选填，明确标题意图用来辅助搜索"
                    value={keywords}
                    onChange={(e) => setKeywords(e.target.value)}
                    className="text-base py-5"
                  />
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 mt-4">
                  <div className="flex gap-3">
                    <Button variant="outline" className="flex items-center gap-2">
                      <Upload className="h-4 w-4" />
                      上传文件
                    </Button>

                    <Button variant="outline" className="flex items-center gap-2">
                      <Globe className="h-4 w-4" />
                      Web检索
                    </Button>
                  </div>

                  <div className="flex items-center gap-3">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="outline" className="flex items-center gap-2">
                          {language === "zh" ? "简体中文" : "English"}
                          <ChevronDown className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setLanguage("zh")}>简体中文</DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setLanguage("en")}>English</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>

                    <Button onClick={handleGenerate} disabled={!topic || isGenerating} className="px-8">
                      {isGenerating ? (
                        "生成中..."
                      ) : (
                        <div className="flex items-center gap-2">
                          <Send className="h-4 w-4" />
                          生成
                        </div>
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* My Documents Section */}
          <div className="mt-8">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-semibold">我的文章</h2>
                <Badge variant="secondary">{tasks.length}</Badge>
              </div>

              <div className="flex items-center gap-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input 
                    placeholder="搜索文章标题" 
                    className="pl-10 w-[250px]" 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <Button 
                  variant="outline" 
                  size="icon"
                  onClick={fetchUserTasks}
                  disabled={isLoadingTasks}
                >
                  <RefreshCw className={`h-4 w-4 ${isLoadingTasks ? 'animate-spin' : ''}`} />
                </Button>
              </div>
            </div>

            {isLoadingTasks ? (
              <div className="flex justify-center py-8">
                <div className="text-center">
                  <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">加载中...</p>
                </div>
              </div>
            ) : filteredTasks.length > 0 ? (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredTasks.map((task) => (
                  <TaskCard key={task.id} task={task} />
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <MessageSquare className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium mb-2">暂无文章</h3>
                <p className="text-muted-foreground">
                  {searchQuery ? '没有找到相关文章' : '开始创建你的第一篇文章吧'}
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}

interface TaskCardProps {
  task: UserTask
}

function TaskCard({ task }: TaskCardProps) {
  // 格式化时间
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // 获取状态显示文本
  const getStatusText = (status: string) => {
    switch (status) {
      case 'pending':
        return '待处理'
      case 'preparing':
        return '准备中'
      case 'searching':
        return '生成查询中'
      case 'searching_web':
        return '搜索网页中'
      case 'crawling':
        return '爬取内容中'
      case 'processing':
        return '处理中'
      case 'completed':
        return '已完成'
      case 'failed':
        return '失败'
      case 'timeout':
        return '超时'
      default:
        return status
    }
  }

  // 获取状态颜色
  const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
    switch (status) {
      case 'completed':
        return 'default'
      case 'preparing':
      case 'searching':
      case 'searching_web':
      case 'crawling':
      case 'processing':
        return 'secondary'
      case 'failed':
      case 'timeout':
        return 'destructive'
      case 'pending':
      default:
        return 'outline'
    }
  }

  return (
    <Card className="overflow-hidden hover:shadow-md transition-shadow h-full">
      <CardContent className="p-0 h-full flex flex-col">
        {/* 内容区域 - 自动扩展 */}
        <div className="flex-1 p-5 space-y-3">
          <h3 className="font-medium line-clamp-2 min-h-[3rem] leading-6">{task.params.topic}</h3>
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">
              创建时间：{formatDate(task.created_at)}
            </p>
            {task.execution_seconds ? (
              <p className="text-sm text-muted-foreground">
                执行时间：{task.execution_seconds.toFixed(1)}秒
              </p>
            ) : (
              <p className="text-sm text-muted-foreground opacity-0">
                执行时间：- 秒
              </p>
            )}
          </div>
        </div>

        {/* 底部操作栏 - 固定在底部 */}
        <div className="flex items-center justify-between px-5 py-3 border-t bg-gray-50/50 dark:bg-gray-800/50">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ThumbsUp className="h-4 w-4" />
            </Button>
            <span className="text-sm">0</span>
          </div>

          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <Badge variant={getStatusVariant(task.status)}>
              {getStatusText(task.status)}
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

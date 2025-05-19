import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Download, Eye } from "lucide-react"

interface HistoryItemProps {
  item: {
    id: string
    topic: string
    language: string
    date: string
    status: string
  }
}

export function HistoryItem({ item }: HistoryItemProps) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex flex-col space-y-2">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <h3 className="font-medium">{item.topic}</h3>
              <div className="flex items-center text-sm text-muted-foreground">
                <span className="mr-2">{item.language === "zh" ? "简体中文" : "英文"}</span>
                <span>{item.date}</span>
              </div>
            </div>
            <div className="flex space-x-2">
              <Button size="sm" variant="outline">
                <Eye className="h-4 w-4 mr-1" />
                查看
              </Button>
              <Button size="sm" variant="outline">
                <Download className="h-4 w-4 mr-1" />
                下载
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

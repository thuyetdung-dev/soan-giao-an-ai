# Schema bảng biến thiên chuẩn

`x` chứa các mốc theo thứ tự. `derivative` xen kẽ dấu trên khoảng và giá trị tại điểm tới hạn. Với 4 mốc, hàng đạo hàm có dạng `["+","0","-","0","+"]`. `values` chứa giá trị hoặc giới hạn của hàm tại từng mốc.

Điểm gián đoạn dùng `discontinuities`, trong đó `index` là vị trí của mốc trong `x`, còn `leftValue` và `rightValue` là hai giới hạn một phía. Bộ dựng sẽ vẽ vạch kép và không nối mũi tên qua điểm này.

```json
{
  "type": "variation_table",
  "x": ["-\\infty", "-1", "1", "+\\infty"],
  "derivative": ["+", "0", "-", "0", "+"],
  "values": ["-\\infty", "4", "0", "+\\infty"]
}
```

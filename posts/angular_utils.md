---
title: AngularJS的工具类集合
date: 2017-08-15
tags: AngularJS
---

#### JSON obj 和 JSON string 相互转换
1. angular.fromJson(), 将JSON字符串解析成一个对象或者数组
```
var json = '{"name": "lily", "age": 20}';
var jsonArr = '[{"name": "tom", "age": 20},{"name": "mike", "age": 19}]';

var obj = angular.fromJson(json);
console.log(obj.name);
var objArr = angular.fromJson(jsonArr);
console.log(objArr[0].name);
console.log(objArr[1].age);

# result
lily
tom
19
```
2. angular.toJson(), 从obj 到json string

```
var obj = {"name": "jeney", "age": 25};
var objArr = [{"name": "tom", "age": 30}, {"name": "god", "age": 50}];
var str = angular.toJson(obj, true);
console.log(str);
var strArr = angular.toJson(objArr, true);
console.log(strArr);

# result
{
  "name": "jeney",
  "age": 25
}
[
  {
    "name": "tom",
    "age": 30
  },
  {
    "name": "god",
    "age": 50
  }
]
```

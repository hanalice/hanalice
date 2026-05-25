---
title: AngularJS中$http服务的简单用法
date: 2017-09-22
tags: AngularJS, Http
---

我们可以使用内置的$http服务直接同外部进行通信。$http服务只是简单的封装了浏览器原生的XMLHttpRequest对象。

### 链式调用

$http服务是只能接受一个参数的函数，这个参数是一个对象，包含了用来生成HTTP请求的
配置内容。这个函数返回一个promise对象，具有success和error两个方法。相当于预定义两个方法，成功的时候执行什么，失败的时候执行什么，并不是同时执行的。
```
$http({
url:'data.json',
method:'GET'
}).success(function(data,header,config,status){
//响应成功

}).error(function(data,header,config,status){
//处理响应失败
});
```

### 可以将$http当做函数来使用，获取mockup的json数据
```
$http({
method:'GET',
url:'/api/users.json',
params:{
'username':'tan'
});
```
其中设置对象可以包含以下主要的键：  
①method: GET/DELETE/HEAD/JSONP/POST/PUT  
②url:绝对的或者相对的请求目标  
③params(字符串map或者对象)
这个键的值是一个字符串map或对象，会被转换成查询字符串追加在URL后面。如果值不是字符串，会被JSON序列化。
比如这个：
```
调用$get方法：
this.getUsers = function () {
    var params = {'sex': "male"};
    var config = (params) ? {'params': params} : {};
    return apiService.get('/api/users/', config)
	.error(function (data) {
	    toastService.add('error', gettext('Unable to retrieve users.'));
	});
};
以上参数会转为？sex=male的形式
```
④data(字符串或者对象)
这个对象中包含了将会被当作消息体发送给服务器的数据。通常在发送POST请求时使用。

### 响应对象

AngularJS传递给then（）方法的响应对象包含了四个属性。  
◇data
这个数据代表转换过后的响应体（如果定义了转换的话）  
◇status
响应的HTTP状态码  
◇headers
这个函数是头信息的getter函数，可以接受一个参数，用来获取对应名字值  

例如，用如下代码获取X-Auth-ID的值：
```
$http({
method: 'GET',
url: '/api/users.json'
}).then (resp) {
// 读取X-Auth-ID
resp.headers('X-Auth-ID');
});
```
◇config
这个对象是用来生成原始请求的完整设置对象。

◇statusText（字符串）
这个字符串是响应的HTTP状态文本。

**success(), error()和then()的区别在于，success和error返回了处理过的数据，没有status和headers,只有具体的data对象**

### 缓存HTTP请求
默认情况下，$http服务不会对请求进行本地缓存。在发送单独的请求时，我们可以通过向$http请求传入一个布尔值或者一个缓存实例来启用缓存。
```
$http.get('/api/users.json',{ cache: true })
.success(function(data) {})
.error(function(data) {});
```

第一次发送请求时，$http服务会向/api/users.json发送一个GET请求。第二次发送同一个GET请求时，$http服务会从缓存中取回请求的结果，而不会真的发送一个HTTP GET请求。
在这个例子里，由于设置了启用缓存，AngularJS默认会使用$cacheFactory,这个服务是AngularJS在启动时自动创建的。如果想要对AngularJS使用的缓存进行更多的自定义控制，可以向请求传入一个自定义的缓存实例代替true。

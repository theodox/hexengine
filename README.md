Next task


Build system: 

1. Make a build setup which builds the game to a wheel
2. use micropip o install


await pyodide.loadPackage("micropip");
const micropip = pyodide.pyimport("micropip");
await micropip.install("https://your.cdn/pkg-1.0-py3-none-any.whl");

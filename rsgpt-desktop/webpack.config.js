const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const webpack = require('webpack');
const ReactRefreshWebpackPlugin = require('@pmmmwh/react-refresh-webpack-plugin');

const isDevelopment = process.env.NODE_ENV !== 'production';

module.exports = (env, argv) => {
  const isProduction = argv && argv.mode === 'production';
  const publicPath = isProduction ? './' : '/';

  return {
  mode: argv?.mode || (isDevelopment ? 'development' : 'production'),
  entry: './src/renderer/index.tsx',
  target: 'web',
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        use: [
          {
            loader: 'ts-loader',
            options: {
              transpileOnly: isDevelopment, // Faster builds in dev
            },
          },
        ],
        exclude: /node_modules/,
      },
      {
        test: /\.css$/i,
        use: ['style-loader', 'css-loader', 'postcss-loader'],
      },
      {
        test: /\.(png|jpe?g|gif|svg|ico)$/i,
        type: 'asset/resource',
        generator: {
          filename: 'assets/[name][ext]',
        },
      },
    ],
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js', '.jsx'],
    fallback: {
      "process": require.resolve("process/browser"),
      "events": require.resolve("events/"),
    },
  },
  output: {
    filename: 'renderer.js',
    path: path.resolve(__dirname, 'dist/renderer'),
    publicPath: publicPath,
    clean: true,
  },
  plugins: [
    new HtmlWebpackPlugin({
      title: 'RSInsight Desktop',
      templateContent: `
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>RSInsight Desktop</title>
          <script>
            window.global = window;
            window.process = window.process || {};
          </script>
        </head>
        <body>
          <div id="root"></div>
        </body>
        </html>
      `,
    }),
    new webpack.ProvidePlugin({
      process: 'process/browser',
    }),
    isDevelopment && new ReactRefreshWebpackPlugin({
      overlay: false, // Disable error overlay in Electron
    }),
  ].filter(Boolean),
  devServer: {
    static: {
      directory: path.join(__dirname, 'dist/renderer'),
    },
    port: 5173,
    hot: true,
    liveReload: false, // Use HMR instead
    headers: {
      'Access-Control-Allow-Origin': '*',
    },
    devMiddleware: {
      writeToDisk: true, // Write files to disk so Electron can load them if needed
    },
  },
  devtool: isDevelopment ? 'eval-source-map' : 'source-map',
  };
};

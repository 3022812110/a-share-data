import React from "react";
import { App as AntApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import "antd/dist/reset.css";

import StockWorkspace from "./StockWorkspace";
import "./styles.css";

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#1677ff",
          colorBgLayout: "#f5f7fb",
          borderRadius: 7,
          fontSize: 11,
          controlHeight: 26,
          controlHeightSM: 22,
          padding: 8,
          paddingSM: 6,
          margin: 8,
          marginSM: 6,
          fontFamily: "'PingFang SC', 'SF Pro Display', sans-serif",
        },
        components: {
          Layout: {
            siderBg: "#ffffff",
            headerBg: "#ffffff",
            bodyBg: "#f5f7fb",
          },
          Menu: {
            itemBg: "#ffffff",
            itemSelectedBg: "#e6f4ff",
            itemSelectedColor: "#1677ff",
            itemHoverBg: "#f5f7fb",
            itemHeight: 30,
          },
          Card: {
            headerHeight: 32,
            paddingLG: 8,
          },
          Table: {
            headerBg: "#fafafa",
            rowHoverBg: "#f5f9ff",
            cellPaddingBlock: 5,
            cellPaddingInline: 7,
            cellPaddingBlockSM: 4,
            cellPaddingInlineSM: 6,
          },
        },
      }}
    >
      <AntApp>
        <StockWorkspace />
      </AntApp>
    </ConfigProvider>
  );
}

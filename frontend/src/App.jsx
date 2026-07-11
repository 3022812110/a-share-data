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
          colorPrimary: "#007aff",
          colorInfo: "#007aff",
          colorSuccess: "#34c759",
          colorWarning: "#ff9f0a",
          colorError: "#ff3b30",
          colorText: "#1d1d1f",
          colorTextSecondary: "#6e6e73",
          colorBorderSecondary: "#e5e5ea",
          colorBgLayout: "#f5f5f7",
          colorBgContainer: "rgba(255,255,255,0.92)",
          borderRadius: 8,
          borderRadiusLG: 10,
          fontSize: 12,
          controlHeight: 28,
          controlHeightSM: 24,
          padding: 8,
          paddingSM: 6,
          margin: 8,
          marginSM: 6,
          fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'PingFang SC', 'Helvetica Neue', sans-serif",
        },
        components: {
          Layout: {
            siderBg: "#ffffff",
            headerBg: "#ffffff",
            bodyBg: "#f5f5f7",
          },
          Menu: {
            itemBg: "#ffffff",
            itemSelectedBg: "rgba(0,122,255,0.10)",
            itemSelectedColor: "#007aff",
            itemHoverBg: "rgba(0,0,0,0.035)",
            itemHeight: 32,
          },
          Card: {
            headerHeight: 32,
            paddingLG: 8,
          },
          Table: {
            headerBg: "rgba(248,248,250,0.96)",
            rowHoverBg: "rgba(0,122,255,0.045)",
            cellPaddingBlock: 4,
            cellPaddingInline: 8,
            cellPaddingBlockSM: 3,
            cellPaddingInlineSM: 7,
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

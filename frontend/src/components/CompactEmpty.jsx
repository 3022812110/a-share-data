import { Empty } from "antd";

export default function CompactEmpty({ description }) {
  return (
    <Empty
      className="compact-empty"
      image={Empty.PRESENTED_IMAGE_SIMPLE}
      description={description}
    />
  );
}

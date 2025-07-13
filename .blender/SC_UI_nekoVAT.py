bl_info = {
    "name": "neko_VAT", #スクリプトの名前
    "author": "nekoco", #作者名
    "version": (2, 0),
    "blender": (4, 1, 1), #Blenderの対応バージョン
    "location": "View3D > Sidebar > View Tab",
    "description": "アニメーションをテクスチャに出力します", #説明文
    "warning": "",
    "doc_url": "",
    "category": "Baking",
}

import bpy
import math
import numpy as np
import struct

class TextureClass:
    def __init__(self, texture_name, width, height):
        self.image = bpy.data.images.get(texture_name)
        if not self.image:
            self.image = bpy.data.images.new(texture_name, width=width, height=height, alpha=True, float_buffer=True)
        elif self.image.size[0] != width or self.image.size[1] != height:
            self.image.scale(width, height)

        self.image.file_format = 'OPEN_EXR'

        self.point = np.array(self.image.pixels[:])
        self.point.resize(height, width * 4)
        self.point[:] = 0

        self.point_R = self.point[::, 0::4]
        self.point_G = self.point[::, 1::4]
        self.point_B = self.point[::, 2::4]
        self.point_A = self.point[::, 3::4]
    
    def SetPixel(self, py, px, r, g, b, a):
        self.point_R[py][px] = r
        self.point_G[py][px] = g
        self.point_B[py][px] = b
        self.point_A[py][px] = a

    def Export(self):
        self.image.pixels = self.point.flatten()


def GetVertexMax(objs, start_frame, end_frame):
    vertex_max = 0
    for frame in range(start_frame, end_frame + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()

        vertex = 0
        for obj in objs:
            mesh = obj.evaluated_get(depsgraph).to_mesh()
            for polygon in mesh.polygons:
                if len(polygon.vertices) >= 4:
                    return -1
                vertex += len(polygon.vertices)
        
        vertex_max = max(vertex_max, vertex)
    return vertex_max

def GetResolution(max_resolution, vertex_num, frame):
    height = -1
    width = -1
    column = 1
    
    for column in range(1, max_resolution + 1):
        for i in range(0, int(math.log2(max_resolution)) + 1):
            if vertex_num <= (1 << i) * column:
                width = 1 << i
                break
        if width != -1:
            break
            
    for i in range(0, int(math.log2(max_resolution)) + 1):
        if frame * column + 1 <= (1 << i):
            height = 1 << i
            break;
    
    return width, height, column

def FixUV(meshs, width, height):
    count = 0
    for mesh in meshs:
        uv_layer = mesh.uv_layers.get("VertexUV")
        if not uv_layer:
            uv_layer = mesh.uv_layers.new(name="VertexUV")
        
        for face in mesh.polygons:
            for i, loop_index in enumerate(face.loop_indices):
                uv_layer.data[loop_index].uv = [
                    count % width / width + 1 / (width * 2),
                    (count // width + 1) / height + 1 / (height * 2)
                    ]
                count += 1

def FixUV_Dupe(meshs, width, height):
    count = 0
    for mesh in meshs:
        uv_layer = mesh.uv_layers.get("VertexUV")
        if not uv_layer:
            uv_layer = mesh.uv_layers.new(name="VertexUV")
        
        seen_vertices = {}
        for vertex in mesh.vertices:
            vertex_co = vertex.co
            # 位置が重複していない場合のみ追加
            if tuple(vertex_co) not in seen_vertices:
                seen_vertices[tuple(vertex_co)] = None
        
        for polygon in mesh.polygons:
            for i, loop_index in enumerate(polygon.loop_indices):
                vertex_co = mesh.vertices[polygon.vertices[i]].co
                if tuple(vertex_co) in seen_vertices:
                    index = list(seen_vertices.keys()).index(tuple(vertex_co)) + count
                    uv_layer.data[loop_index].uv = [
                        index % width / width + 1 / (width * 2),
                        (index // width + 1) / height + 1 / (height * 2)
                        ]
                    
        count += len(seen_vertices)
    
def NormalToFloat(x, y, z):
    x_8bit, y_8bit, z_8bit = map(lambda v: int((v / 2 + 0.5) * 255), (x, y, z))
    packed_24bit = (x_8bit << 16) | (y_8bit << 8) | z_8bit
    return struct.unpack('!f', struct.pack('!I', packed_24bit | 0x40000000))[0]

# 各値0~16384まで
def ShortsToFloat(value1, value2):
    paced_32bit = (value1 << 16) | value2
    return struct.unpack('!f', struct.pack('!I', paced_32bit | 0x40000000))[0]

def CreateObject(polygon_count, objs):
    mesh = bpy.data.meshes.new(name="TriangleMesh")
    obj = bpy.data.objects.new("TriangleObject", mesh)
    bpy.context.collection.objects.link(obj)

    vertices = []
    faces = []
    for p in range(polygon_count):
        vertices.append((1, 0, p * 0.001))
        vertices.append((-1, 0, p * 0.001))
        vertices.append((0, 1, p * 0.001))
        faces.append((p * 3, p * 3 + 1, p * 3 + 2))

    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    polygon_count_idle = sum([len(obj.data.polygons) for obj in objs])
    if polygon_count_idle == polygon_count:
        # copy UV from objs
        uv_layer = mesh.uv_layers.new(name="UV0")
        vert_index = 0
        for obj in objs:
            original_uv_layer = obj.data.uv_layers[0]
            if not original_uv_layer:
                vert_index += 3 * len(obj.data.polygons)
                continue
            for polygon in obj.data.polygons:
                for loop_index in polygon.loop_indices:
                    uv_layer.uv[vert_index].vector = original_uv_layer.uv[loop_index].vector
                    vert_index += 1



def Main_UV(objs, max_resolution, hard_edge, vertex_compress):
    if vertex_compress:
        hard_edge = False

    start_frame = bpy.context.scene.frame_start
    end_frame = bpy.context.scene.frame_end
    vertex_num = sum(len(obj.data.vertices) for obj in objs) \
        if vertex_compress \
        else len([loop for obj in objs for polygon in obj.data.polygons for loop in polygon.loop_indices])
    width, height, column = GetResolution(max_resolution, vertex_num, end_frame - start_frame + 1)

    if width == -1 or height == -1:
        print("頂点数またはフレーム数が大きすぎます")
        return
    
    texture = TextureClass(objs[0].name + '_pos', width, height)

    param = [ShortsToFloat(column, end_frame - start_frame), 0, 0, 1]
    texture.SetPixel(0, 0, *param)

    bpy.context.scene.frame_set(0)
    origins = {}
    for obj in objs:
        origins[obj] = obj.location.copy()

    if vertex_compress:
        FixUV_Dupe([obj.data for obj in objs], width, height)
    else:
        FixUV([obj.data for obj in objs], width, height)
    
    for frame in range(start_frame, end_frame + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for obj in objs:
            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()
            uv_layer = eval_obj.data.uv_layers.get("VertexUV")
            for polygon in mesh.polygons:
                for i, loop_index in enumerate(polygon.loop_indices):
                    uv = uv_layer.data[loop_index].uv
                    pixel = [int(uv.y * height), int(uv.x * width)]
                    pixel[0] += (frame - start_frame) * column

                    vertex_pos = obj.matrix_world @ mesh.vertices[polygon.vertices[i]].co - origins[obj]
                    normal = obj.matrix_world @ polygon.normal - obj.matrix_world.translation \
                        if hard_edge \
                        else obj.matrix_world @ mesh.vertices[polygon.vertices[i]].normal - obj.matrix_world.translation
                    normal = normal.normalized()

                    texture.SetPixel(*pixel, *vertex_pos, NormalToFloat(*normal))

    texture.Export()

def Main_VertexID(objs, max_resolution, hard_edge):
    start_frame = bpy.context.scene.frame_start
    end_frame = bpy.context.scene.frame_end
    vertex_max = GetVertexMax(objs, start_frame, end_frame)
    if vertex_max == -1:
        print("三角形以外のポリゴンが含まれています")
        return

    width, height, column = GetResolution(max_resolution, vertex_max, end_frame - start_frame + 1)
    if width == -1 or height == -1:
        print("頂点数またはフレーム数が大きすぎます")
        return
    
    texture = TextureClass(objs[0].name + '_pos', width, height)

    param = [ShortsToFloat(column, end_frame - start_frame), 0, 0, 1]
    texture.SetPixel(0, 0, *param)

    for frame in range(start_frame, end_frame + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()

        count = 0
        for obj in objs:
            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()
            for polygon in mesh.polygons:
                for i, loop_index in enumerate(polygon.loop_indices):
                    pixel = [count // width + 1, count % width]
                    pixel[0] += (frame - start_frame) * column

                    vertex_pos = obj.matrix_world @ mesh.vertices[polygon.vertices[i]].co
                    normal = obj.matrix_world @ polygon.normal - obj.matrix_world.translation \
                        if hard_edge \
                        else obj.matrix_world @ mesh.vertices[polygon.vertices[i]].normal - obj.matrix_world.translation
                    normal = normal.normalized()

                    texture.SetPixel(*pixel, *vertex_pos, NormalToFloat(*normal))

                    count += 1

    texture.Export()
    CreateObject(math.ceil(vertex_max / 3), objs)


class HelloWorldPanel(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "neko/VAT Panel"
    bl_idname = "OBJECT_PT_custom_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VAT'

    def draw(self, context):
        layout = self.layout
        obj = context.object
        scene = context.scene

        layout.row().label(text="Active object is: " + obj.name)
        layout.prop(scene, "max_resolution", text=f"最大サイズ:{2 ** scene.max_resolution}")
        if not scene.mock_object:
            layout.prop(scene, "vertex_compress", text="頂点情報圧縮")
        if not scene.vertex_compress:
            layout.prop(scene, "mock_object", text="モックオブジェクト作成")
            layout.prop(scene, "hard_edge", text="フラットシェード")
        layout.row().operator("object.simple_operator")


class SimpleOperator(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "object.simple_operator"
    bl_label = "Execute"

    def execute(self, context):
        scene = context.scene

        objs = bpy.context.selected_objects
        max_resolution = 2 ** scene.max_resolution
        vertex_compress = scene.vertex_compress
        mock_object = scene.mock_object
        hard_edge = scene.hard_edge

        if vertex_compress:
            mock_object = False
            hard_edge = False

        if mock_object:
            vertex_compress = False
        
        if mock_object:
            Main_VertexID(objs, max_resolution, hard_edge)
        else:
            Main_UV(objs, max_resolution, hard_edge, vertex_compress)

        return {'FINISHED'}


def register():
    bpy.utils.register_class(HelloWorldPanel)
    bpy.utils.register_class(SimpleOperator)

    bpy.types.Scene.max_resolution = bpy.props.IntProperty(
        name="Max Resolution",
        description="テクスチャを出力する際の最大テクスチャサイズ",
        default=10,
        min=4,
        max=13
    )
    bpy.types.Scene.vertex_compress = bpy.props.BoolProperty(
        name="Vertex Compress",
        description="頂点情報を圧縮するか",
        default=False
    )
    bpy.types.Scene.mock_object = bpy.props.BoolProperty(
        name="Mock Object",
        description="マテリアル適応用の別オブジェクトを作成するか",
        default=False
    )
    bpy.types.Scene.hard_edge = bpy.props.BoolProperty(
        name="Hard Edge",
        description="法線をフラットシェードで出力するか",
        default=False
    )
    

def unregister():
    bpy.utils.unregister_class(HelloWorldPanel)
    bpy.utils.unregister_class(SimpleOperator)

    del bpy.types.Scene.max_resolution
    del bpy.types.Scene.vertex_compress
    del bpy.types.Scene.mock_object
    del bpy.types.Scene.hard_edge

if __name__ == "__main__":
    register()
